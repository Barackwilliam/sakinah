"""Advertise with us: vendors choose a package, describe their service, pay by mobile money and go live once the payment
is confirmed. The advert then runs for the package's number of days and drops off the site on its own when it ends."""
import secrets
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


def new_token(): return secrets.token_urlsafe(12)


def unique_slug(model, text, field="slug"):
    base = slugify(text)[:60] or "advert"
    slug, i = base, 2
    while model.objects.filter(**{field: slug}).exists():
        slug, i = f"{base}-{i}", i + 1
    return slug


class AdPackage(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    tagline = models.CharField(max_length=120, blank=True)
    price = models.PositiveIntegerField(help_text=_("Price for the whole period, in TSh."))
    days = models.PositiveSmallIntegerField(default=30, help_text=_("How many days the advert stays on the site."))
    features = models.TextField(blank=True, help_text=_("One per line. Start a line with - for something the package does not include."))
    featured = models.BooleanField(default=False, help_text=_("Featured badge and first place in its category."))
    home_page = models.BooleanField(default=False, help_text=_("Also shown in Featured Vendors on the home page."))
    max_photos = models.PositiveSmallIntegerField(default=1, help_text=_("Photos the vendor may upload (1 to 4)."))
    popular = models.BooleanField(default=False, verbose_name=_("Most popular"))
    active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta: ordering = ["order", "price"]
    def __str__(self): return self.name

    @property
    def feature_list(self):
        """Starter wording is translated (core/content_strings.py); the admin's own wording shows as typed."""
        from django.utils.translation import gettext
        return [(not l.startswith("-"), gettext(l.lstrip("-+ ").strip())) for l in self.features.splitlines() if l.strip()]

    @property
    def per_day(self): return round(self.price / self.days) if self.days else self.price


class AdOrder(models.Model):
    """One vendor's advert request, from the form to the live advert, including renewals."""
    STATUS = [("awaiting_payment", _("Awaiting payment")), ("paid", _("Payment sent - being confirmed")),
              ("live", _("Live")), ("rejected", _("Not approved"))]
    token = models.CharField(max_length=32, unique=True, default=new_token, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="ad_orders")
    package = models.ForeignKey(AdPackage, on_delete=models.PROTECT, related_name="orders")
    business_name = models.CharField(_("Business name"), max_length=100)
    contact_name = models.CharField(_("Your name"), max_length=80)
    phone = models.CharField(_("Phone / WhatsApp"), max_length=20)
    email = models.EmailField(_("Email (optional)"), blank=True)
    category = models.ForeignKey("core.ServiceCategory", on_delete=models.PROTECT, related_name="ad_orders", verbose_name=_("Service category"))
    city = models.CharField(_("City"), max_length=60)
    title = models.CharField(_("Advert title"), max_length=120)
    description = models.TextField(_("Describe your service"), max_length=2000)
    price = models.PositiveIntegerField(_("Starting price (TSh)"), default=0)
    price_unit = models.CharField(_("Price is per"), max_length=40, default="Per Event / Day")
    negotiable = models.BooleanField(_("Price is negotiable"), default=False)
    image = models.ImageField(_("Main photo"), upload_to="adverts/")
    photo2 = models.ImageField(upload_to="adverts/", blank=True)
    photo3 = models.ImageField(upload_to="adverts/", blank=True)
    photo4 = models.ImageField(upload_to="adverts/", blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="awaiting_payment", db_index=True)
    advert = models.ForeignKey("core.Advert", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    admin_note = models.TextField(_("Note to the vendor"), blank=True, help_text=_("Shown on the vendor's order page, e.g. why it was not approved."))
    created = models.DateTimeField(auto_now_add=True)
    published = models.DateTimeField(null=True, blank=True)

    class Meta: ordering = ["-created"]
    def __str__(self): return f"{self.business_name} - {self.title}"
    def get_absolute_url(self): return reverse("ad_order", args=[self.token])

    @property
    def photos(self): return [p for p in (self.image, self.photo2, self.photo3, self.photo4) if p]
    @property
    def expires(self): return self.advert.expires if self.advert_id else None
    @property
    def is_expired(self): return bool(self.expires and self.expires < timezone.localdate())
    @property
    def days_left(self): return max((self.expires - timezone.localdate()).days, 0) if self.expires else 0
    @property
    def payment(self):
        """The latest payment for this advert (first payment or a renewal)."""
        if not hasattr(self, "_payment"): self._payment = self.payments.order_by("-created", "-pk").first() if self.pk else None
        return self._payment
    @property
    def payment_pending(self): return bool(self.payment and self.payment.status == "pending")
    @property
    def step(self):
        """1 sent, 2 paid, 3 being checked, 4 live (for the progress bar)."""
        return {"awaiting_payment": 1, "paid": 3, "live": 4}.get(self.status, 1)

    def publish(self, request=None):
        """Turn the request into a live advert (or extend it on a renewal) for the package's number of days."""
        from .models import Advert, AdvertPhoto, Notification, Vendor
        today = timezone.localdate()
        vendor = (self.advert.vendor if self.advert_id else
                  Vendor.objects.filter(phone=self.phone).first() or
                  Vendor.objects.create(name=self.business_name, slug=unique_slug(Vendor, self.business_name), city=self.city, phone=self.phone))
        ad = self.advert
        if ad is None:
            ad = Advert.objects.create(category=self.category, vendor=vendor, title=self.title, slug=unique_slug(Advert, self.title),
                                       city=self.city, price=self.price, price_unit=self.price_unit, negotiable=self.negotiable,
                                       description=self.description, image=self.image.name, map_query=f"{self.city}, Tanzania")
            for i, p in enumerate([self.photo2, self.photo3, self.photo4]):
                if p: AdvertPhoto.objects.create(advert=ad, image=p.name, order=i)
        start = max(ad.expires or today, today) if self.advert_id else today
        ad.expires, ad.active, ad.package = start + timedelta(days=self.package.days), True, self.package
        ad.featured = ad.featured or self.package.featured
        ad.save(update_fields=["expires", "active", "package", "featured"])
        first = not self.advert_id
        self.advert, self.status, self.published = ad, "live", self.published or timezone.now()
        self.save(update_fields=["advert", "status", "published"])
        if self.user_id:
            Notification.objects.create(user=self.user, link=self.get_absolute_url(),
                                        title=(f"Your advert is live: {ad.title}" if first else f"Your advert is renewed: {ad.title}")[:120],
                                        body=f"It runs until {ad.expires:%d %b %Y}.")
        self.email_vendor(first, request.build_absolute_uri(self.get_absolute_url()) if request else self.get_absolute_url())
        return ad

    def email_vendor(self, first, link):
        if not self.email or not getattr(settings, "EMAIL_LIVE", False): return
        from django.core.mail import send_mail
        try:
            send_mail(f"{'Tangazo lako liko hewani' if first else 'Tangazo lako limehuishwa'} - {self.title}",
                      f"Hongera {self.contact_name}!\n\n\"{self.title}\" is live on Sakinah until {self.expires:%d %b %Y}.\n"
                      f"Track it here: {link}\n", None, [self.email], fail_silently=True)
        except Exception:
            pass
