"""Banner adverts: one picture with a link, shown in a fixed place on the site (home page, beside pages, inside the
member dashboard). Advertisers book a place from their dashboard and pay with Pesapal; our team approves the picture,
then it runs for the place's number of days, taking turns with the other banners booked there, and stops on its own."""
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models_ads import new_token


class BannerSlot(models.Model):
    PLACES = [("home", _("Home page, full width")), ("sidebar", _("Sidebar square")), ("dashboard", _("Member dashboard"))]
    SIZES = {"home": (1200, 300), "sidebar": (600, 600), "dashboard": (1200, 250)}   # pictures are cropped to these
    place = models.CharField(max_length=12, choices=PLACES, unique=True)
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=200, blank=True)
    price = models.PositiveIntegerField(help_text=_("Price for the whole period, in TSh."))
    days = models.PositiveSmallIntegerField(default=30, help_text=_("How many days a banner runs, e.g. 30."))
    max_live = models.PositiveSmallIntegerField(default=3, verbose_name=_("Banners at the same time"),
                                                help_text=_("How many banners may run here at once. They take turns on each page view."))
    active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]
        verbose_name, verbose_name_plural = _("Banner place"), _("Banner places")
    def __str__(self): return self.name

    @property
    def size(self): return self.SIZES.get(self.place, (1200, 300))
    @property
    def size_text(self): return "%d × %d px" % self.size
    @property
    def run_days(self):
        """Squeezed while testing, like advert packages: 30 days become 3 when a month is 3 days."""
        from .models import SiteSetting
        per = SiteSetting.load().days_per_month
        return self.days if per >= 30 else max(1, -(-self.days * per // 30))
    def taken(self):
        """Banners running now or paid and waiting for approval."""
        today = timezone.localdate()
        return self.orders.filter(models.Q(status="live", expires__gte=today) | models.Q(status="review")).count()
    @property
    def free(self): return max(0, self.max_live - self.taken())


class BannerQuerySet(models.QuerySet):
    def live(self):
        return self.filter(status="live", starts__lte=timezone.localdate(), expires__gte=timezone.localdate())


class BannerOrder(models.Model):
    STATUS = [("awaiting_payment", _("Awaiting payment")), ("review", _("Paid - waiting for approval")), ("live", _("Live")),
              ("paused", _("Paused")), ("rejected", _("Not approved"))]
    objects = BannerQuerySet.as_manager()
    token = models.CharField(max_length=32, unique=True, default=new_token, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="banner_orders")
    slot = models.ForeignKey(BannerSlot, on_delete=models.PROTECT, related_name="orders", verbose_name=_("Place"))
    business_name = models.CharField(_("Business name"), max_length=100)
    title = models.CharField(_("Short description"), max_length=80, help_text=_("Read aloud to people who cannot see the picture."))
    link = models.CharField(_("Link"), max_length=300, help_text=_("Where people go when they tap the banner: your website, or a WhatsApp number."))
    image = models.ImageField(_("Banner picture"), upload_to="banners/")
    status = models.CharField(max_length=20, choices=STATUS, default="awaiting_payment", db_index=True)
    starts = models.DateField(null=True, blank=True)
    expires = models.DateField(null=True, blank=True, help_text=_("Last day on the site."))
    views = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    admin_note = models.TextField(_("Note to the advertiser"), blank=True, help_text=_("Shown on the advertiser's banner page, e.g. why it was not approved."))
    created = models.DateTimeField(auto_now_add=True)
    published = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]
        verbose_name, verbose_name_plural = _("Banner"), _("Banners")
    def __str__(self): return f"{self.business_name} - {self.slot}"
    def get_absolute_url(self): return reverse("ad_banner", args=[self.token])

    @property
    def target(self):
        """The link as a real address: a phone number becomes a WhatsApp chat."""
        l = self.link.strip()
        digits = "".join(c for c in l if c.isdigit())
        if not l.lower().startswith(("http://", "https://")) and 9 <= len(digits) <= 15:
            if digits.startswith("0"): digits = "255" + digits[1:]
            return f"https://wa.me/{digits}"
        return l if l.lower().startswith(("http://", "https://")) else "https://" + l
    @property
    def is_expired(self): return bool(self.expires and self.expires < timezone.localdate())
    @property
    def is_live(self): return self.status == "live" and not self.is_expired
    @property
    def days_left(self): return max((self.expires - timezone.localdate()).days, 0) if self.expires else 0
    @property
    def ctr(self): return round(self.clicks * 100 / self.views, 1) if self.views else 0
    @property
    def payment(self):
        if not hasattr(self, "_payment"): self._payment = self.payments.order_by("-created", "-pk").first() if self.pk else None
        return self._payment
    @property
    def payment_pending(self): return bool(self.payment and self.payment.status == "pending")
    @property
    def step(self): return {"awaiting_payment": 1, "review": 2, "live": 3, "paused": 3}.get(self.status, 1)

    def paid(self, request=None):
        """A payment went through: a running banner is extended straight away; a new one waits for our team's approval."""
        from django.contrib.auth import get_user_model
        from .models import Notification
        if self.is_live: return self.go_live(request)
        self.status = "review"; self.save(update_fields=["status"])
        for staff in get_user_model().objects.filter(is_staff=True, is_active=True):
            Notification.objects.create(user=staff, link=reverse("dash_manage_edit", args=["banners", self.pk]),
                                        title=f"Banner to approve: {self.business_name}"[:120], body=f"{self.slot.name} · {self.title}"[:2000])
        return None

    def go_live(self, request=None):
        """Publish (or extend) the banner for the place's number of days."""
        from .models import Notification
        today = timezone.localdate()
        first = not self.is_live
        start = self.expires + timedelta(days=1) if not first else today
        self.starts = self.starts if not first else today
        self.expires = start + timedelta(days=self.slot.run_days - 1)
        self.status, self.published = "live", self.published or timezone.now()
        self.save(update_fields=["starts", "expires", "status", "published"])
        if self.user_id:
            Notification.objects.create(user=self.user, link=self.get_absolute_url(),
                                        title=(f"Your banner is live: {self.business_name}" if first else f"Your banner is renewed: {self.business_name}")[:120],
                                        body=f"It runs until {self.expires:%d %b %Y}.")
        return self.expires
