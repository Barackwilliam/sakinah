from django.conf import settings
from django.db import models
from django.urls import reverse
import calendar
from datetime import timedelta
from django.utils import timezone

class SiteSetting(models.Model):
    """Everything editable in header/footer/hero lives here (no hardcoded text)."""
    brand = models.CharField(max_length=50, default="Sakinah")
    tagline = models.CharField(max_length=100, default="Imani • Mapenzi • Ndoa")
    hero_title_1 = models.CharField(max_length=100, default="Find Someone Special.")
    hero_title_2 = models.CharField(max_length=100, default="Build a Marriage.")
    hero_text = models.CharField(max_length=250, default="Connect with verified people who are looking for meaningful relationships and marriage.")
    hero_quote = models.CharField(max_length=200, default="Zaidi ya uchumba, ni safari ya maisha na mwenye kheri.")
    hero_image = models.ImageField(upload_to="site/", blank=True)
    logo = models.ImageField(upload_to="site/", blank=True)
    premium_image = models.ImageField(upload_to="site/", blank=True, help_text="Couple photo on the Go Premium card")
    advert_image = models.ImageField(upload_to="site/", blank=True, help_text="Photo on the Advertise Your Marriage Service card")
    currency = models.CharField(max_length=10, default="TSh")
    offer_text = models.CharField(max_length=160, blank=True, help_text="Premium page special offer. Leave blank to hide the offer.")
    contact_email = models.EmailField(blank=True)
    contact_whatsapp = models.CharField(max_length=20, blank=True, help_text="WhatsApp number with country code, e.g. 255712345678")
    @property
    def contact_url(self):
        digits = "".join(c for c in self.contact_whatsapp if c.isdigit())
        return f"https://wa.me/{digits}" if digits else (f"mailto:{self.contact_email}" if self.contact_email else "")
    class Meta: verbose_name = "Site setting"
    @classmethod
    def load(cls):
        return cls.objects.first() or cls()
    def __str__(self): return self.brand

class Plan(models.Model):
    name = models.CharField(max_length=50)
    price = models.PositiveIntegerField(default=0)
    order = models.PositiveSmallIntegerField(default=0)
    tagline = models.CharField(max_length=100, blank=True)
    period = models.CharField(max_length=30, default="per month")
    features = models.TextField(blank=True, help_text="One feature per line. Start a line with - for a feature the plan does not include.")
    popular = models.BooleanField(default=False, verbose_name="Most popular")
    icon = models.ImageField(upload_to="plans/", blank=True)
    @property
    def feature_list(self):
        return [(not l.startswith("-"), l.lstrip("-+ ").strip()) for l in self.features.splitlines() if l.strip()]
    class Meta: ordering = ["order"]
    def __str__(self): return self.name

class PremiumPerk(models.Model):
    text = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=0)
    class Meta: ordering = ["order"]
    def __str__(self): return self.text

class Member(models.Model):
    GENDER = [("F", "Woman"), ("M", "Man")]
    RELIGION = [("Islam", "Muislamu"), ("Christian", "Mkristo")]
    MARITAL = [("single", "Single"), ("divorced", "Divorced"), ("widowed", "Widowed")]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="member")
    name = models.CharField(max_length=80)
    age = models.PositiveSmallIntegerField()
    gender = models.CharField(max_length=1, choices=GENDER)
    city = models.CharField(max_length=60)
    occupation = models.CharField(max_length=80)
    education = models.CharField(max_length=80, blank=True)
    marital_status = models.CharField(max_length=10, choices=MARITAL, default="single")
    origin = models.CharField(max_length=40, default="Mtanzania")
    intention = models.CharField(max_length=60, default="Marriage-oriented")
    religion = models.CharField(max_length=30, choices=RELIGION, default="Islam")
    goal = models.CharField(max_length=160, blank=True, help_text="Lengo. Leave blank for the default text.")
    bio = models.TextField(max_length=600, blank=True)
    photo = models.ImageField(upload_to="members/", blank=True)
    phone = models.CharField(max_length=20, blank=True, help_text="WhatsApp number with country code, e.g. 255712345678")
    whatsapp_ok = models.BooleanField(default=False, verbose_name="Allow WhatsApp messages")
    verified = models.BooleanField(default=False)
    featured = models.BooleanField(default=False)
    compatibility = models.PositiveSmallIntegerField(default=80)
    joined = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(null=True, blank=True)
    plan = models.ForeignKey("Plan", on_delete=models.SET_NULL, null=True, blank=True, related_name="members")
    premium_until = models.DateField(null=True, blank=True)
    # quick info and lifestyle
    height_cm = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Height (cm)")
    body_type = models.CharField(max_length=40, blank=True)
    languages = models.CharField(max_length=120, default="Swahili, English", blank=True)
    workplace = models.CharField(max_length=120, blank=True)
    income_range = models.CharField(max_length=60, blank=True)
    smokes = models.BooleanField(default=False)
    drinks = models.BooleanField(default=False)
    willing_to_relocate = models.CharField(max_length=40, blank=True)
    food_preference = models.CharField(max_length=60, default="Halal", blank=True)
    hobbies = models.CharField(max_length=200, blank=True)
    exercise = models.CharField(max_length=60, blank=True)
    # religion and values
    prayer = models.CharField(max_length=80, blank=True)
    hijab = models.CharField(max_length=40, blank=True, verbose_name="Hijab / dress")
    quran_reading = models.CharField(max_length=60, blank=True, verbose_name="Qur'an / scripture reading")
    values = models.CharField(max_length=200, blank=True)
    # family
    father_status = models.CharField(max_length=40, blank=True)
    mother_status = models.CharField(max_length=40, blank=True)
    siblings = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Number of siblings")
    family_type = models.CharField(max_length=40, blank=True)
    family_location = models.CharField(max_length=80, blank=True)
    about_family = models.CharField(max_length=200, blank=True)
    # partner preferences
    pref_age_min = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Preferred age from")
    pref_age_max = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Preferred age to")
    pref_marital = models.CharField(max_length=60, blank=True, verbose_name="Preferred marital status")
    pref_location = models.CharField(max_length=80, blank=True, verbose_name="Preferred location")
    pref_education = models.CharField(max_length=80, blank=True, verbose_name="Preferred education")
    pref_occupation = models.CharField(max_length=80, blank=True, verbose_name="Preferred occupation")
    pref_prayer = models.CharField(max_length=80, blank=True, verbose_name="Preferred prayer habit")
    pref_values = models.CharField(max_length=200, blank=True, verbose_name="Preferred values")
    pref_relocate = models.CharField(max_length=40, blank=True, verbose_name="Partner willing to relocate")
    pref_more = models.CharField(max_length=200, blank=True, verbose_name="Additional preferences")
    class Meta: ordering = ["-featured", "-verified", "-joined"]
    def __str__(self): return f"{self.name}, {self.age}"

    @property
    def seeking(self): return "Mke wa Ndoa" if self.gender == "M" else "Mume wa Ndoa"
    @property
    def marital(self):
        return {"single": "Hajaoa" if self.gender == "M" else "Hajaolewa", "divorced": "Ameachika",
                "widowed": "Mgane" if self.gender == "M" else "Mjane"}[self.marital_status]
    @property
    def goal_text(self):
        return self.goal or f"Ndoa yenye utulivu, upendo, heshima na misingi ya {'Kiislamu' if self.religion == 'Islam' else 'Kikristo'}."
    @property
    def is_online(self): return bool(self.last_seen and timezone.now() - self.last_seen < timedelta(minutes=5))
    @property
    def photo_total(self):
        extra = getattr(self, "extra_photos", None)
        return int(bool(self.photo)) + (self.photos.count() if extra is None else extra)
    @property
    def whatsapp_url(self):
        digits = "".join(c for c in self.phone if c.isdigit())
        return f"https://wa.me/{digits}" if self.whatsapp_ok and digits else ""

    @property
    def pronoun(self): return "Her" if self.gender == "F" else "His"
    @property
    def is_premium(self): return bool(self.plan_id and self.premium_until and self.premium_until >= timezone.localdate())

class MemberPhoto(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="members/")
    order = models.PositiveSmallIntegerField(default=0)
    class Meta: ordering = ["order", "pk"]

class Like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="likes")
    created = models.DateTimeField(auto_now_add=True)
    class Meta: constraints = [models.UniqueConstraint(fields=["user", "member"], name="unique_like")]
    def __str__(self): return f"{self.user} -> {self.member}"

class ServiceCategory(models.Model):
    name = models.CharField(max_length=60)
    slug = models.SlugField(unique=True)
    blurb = models.CharField(max_length=80)
    image = models.ImageField(upload_to="services/", blank=True)
    button_label = models.CharField(max_length=30, default="View Advert")
    order = models.PositiveSmallIntegerField(default=0)
    class Meta: ordering = ["order"]; verbose_name_plural = "Service categories"
    def __str__(self): return self.name

class EventCategory(models.Model):
    name = models.CharField(max_length=60)
    slug = models.SlugField(unique=True)
    order = models.PositiveSmallIntegerField(default=0)
    class Meta: ordering = ["order"]; verbose_name_plural = "Event categories"
    def __str__(self): return self.name

class Event(models.Model):
    title = models.CharField(max_length=120)
    category = models.ForeignKey(EventCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="events")
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    city = models.CharField(max_length=60)
    description = models.CharField(max_length=200, blank=True)
    image = models.ImageField(upload_to="events/", blank=True)
    attendees = models.PositiveIntegerField(default=0, help_text="People already going before online registration (e.g. walk-ins).")
    class Meta: ordering = ["date"]
    def __str__(self): return self.title
    @property
    def going(self):
        n = getattr(self, "reg_count", None)
        return self.attendees + (self.registrations.count() if n is None else n)

class FeatureStrip(models.Model):
    """Bottom icon strip on home."""
    title = models.CharField(max_length=50)
    text = models.CharField(max_length=80)
    icon = models.CharField(max_length=30, default="heart")
    order = models.PositiveSmallIntegerField(default=0)
    class Meta: ordering = ["order"]

class Message(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    to = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="inbox")
    body = models.TextField(max_length=1000)
    created = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    class Meta: ordering = ["created"]
    def __str__(self): return f"{self.sender} -> {self.to}: {self.body[:30]}"


class EventRegistration(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="registrations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_registrations")
    created = models.DateTimeField(auto_now_add=True)
    class Meta: constraints = [models.UniqueConstraint(fields=["event", "user"], name="unique_event_registration")]

class Shortlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shortlist")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="shortlisted_by")
    created = models.DateTimeField(auto_now_add=True)
    class Meta: constraints = [models.UniqueConstraint(fields=["user", "member"], name="unique_shortlist")]

class Report(models.Model):
    REASONS = [("fake", "Fake profile"), ("rude", "Rude or offensive"), ("scam", "Scam or asking for money"), ("other", "Other")]
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="reports")
    reason = models.CharField(max_length=10, choices=REASONS)
    details = models.TextField(max_length=1000, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)
    def __str__(self): return f"{self.member} ({self.get_reason_display()})"

# ----- marriage services marketplace -----
class Vendor(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to="vendors/", blank=True)
    city = models.CharField(max_length=60)
    verified = models.BooleanField(default=False)
    member_since = models.DateField(default=timezone.now)
    phone = models.CharField(max_length=20, blank=True)
    why_choose = models.TextField(blank=True, help_text="One reason per line.")
    def __str__(self): return self.name
    @property
    def reasons(self): return [l.strip() for l in self.why_choose.splitlines() if l.strip()]

class Advert(models.Model):
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name="adverts")
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="adverts")
    title = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    city = models.CharField(max_length=60)
    image = models.ImageField(upload_to="adverts/", blank=True)
    price = models.PositiveIntegerField(default=0)
    price_unit = models.CharField(max_length=40, default="Per Event / Day")
    negotiable = models.BooleanField(default=False)
    featured = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    highlights = models.TextField(blank=True, help_text="One per line as icon|text, e.g. people|Up to 300 Guests. Icons: people, parking, snow, food, camera, star.")
    includes = models.TextField(blank=True, help_text="Package includes, one per line.")
    extras = models.TextField(blank=True, help_text="Optional additional services, one per line.")
    availability = models.CharField(max_length=200, blank=True)
    details = models.TextField(blank=True, help_text="Extra details, one per line as Label|Value.")
    map_query = models.CharField(max_length=160, blank=True, help_text="Address used for the map, e.g. Kariakoo, Dar es Salaam")
    views = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["-featured", "-created"]
    def __str__(self): return self.title
    def _lines(self, text): return [l.strip() for l in text.splitlines() if l.strip()]
    @property
    def highlight_list(self): return [(l.split("|", 1) + [""])[:2] if "|" in l else ["star", l] for l in self._lines(self.highlights)]
    @property
    def include_list(self): return self._lines(self.includes)
    @property
    def extra_list(self): return self._lines(self.extras)
    @property
    def detail_list(self): return [l.split("|", 1) for l in self._lines(self.details) if "|" in l]

class AdvertPhoto(models.Model):
    advert = models.ForeignKey(Advert, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="adverts/")
    order = models.PositiveSmallIntegerField(default=0)
    class Meta: ordering = ["order", "pk"]

class AdvertReview(models.Model):
    advert = models.ForeignKey(Advert, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="advert_reviews")
    rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(max_length=1000, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created"]
        constraints = [models.UniqueConstraint(fields=["advert", "user"], name="unique_advert_review")]

class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist")
    advert = models.ForeignKey(Advert, on_delete=models.CASCADE, related_name="wishlisted_by")
    created = models.DateTimeField(auto_now_add=True)
    class Meta: constraints = [models.UniqueConstraint(fields=["user", "advert"], name="unique_wishlist")]

class Inquiry(models.Model):
    KINDS = [("availability", "Check availability"), ("inquiry", "Inquiry")]
    advert = models.ForeignKey(Advert, on_delete=models.CASCADE, related_name="inquiries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    kind = models.CharField(max_length=12, choices=KINDS, default="inquiry")
    name = models.CharField(max_length=80)
    phone = models.CharField(max_length=20)
    event_date = models.DateField(null=True, blank=True)
    guests = models.PositiveIntegerField(null=True, blank=True)
    message = models.TextField(max_length=1000, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)
    class Meta: ordering = ["-created"]; verbose_name_plural = "Inquiries"
    def __str__(self): return f"{self.name} - {self.advert}"

# ----- articles -----
class ArticleCategory(models.Model):
    name = models.CharField(max_length=60)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=30, default="book")
    order = models.PositiveSmallIntegerField(default=0)
    class Meta: ordering = ["order"]; verbose_name_plural = "Article categories"
    def __str__(self): return self.name

class Article(models.Model):
    title = models.CharField(max_length=160)
    slug = models.SlugField(unique=True, max_length=180)
    category = models.ForeignKey(ArticleCategory, on_delete=models.SET_NULL, null=True, related_name="articles")
    author = models.CharField(max_length=80, default="Sakinah Team")
    image = models.ImageField(upload_to="articles/", blank=True)
    excerpt = models.CharField(max_length=240)
    body = models.TextField()
    tags = models.CharField(max_length=200, blank=True, help_text="Comma separated, e.g. Nikah, Communication")
    published = models.DateField(default=timezone.now)
    featured = models.BooleanField(default=False)
    views = models.PositiveIntegerField(default=0)
    class Meta: ordering = ["-published", "-pk"]
    def __str__(self): return self.title
    def get_absolute_url(self): return reverse("article", args=[self.slug])
    @property
    def tag_list(self): return [t.strip() for t in self.tags.split(",") if t.strip()]

class ArticleComment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField(max_length=1000)
    created = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["created"]


# ----- payments, notifications and admin communications -----
class Payment(models.Model):
    KINDS = [("premium", "Premium plan"), ("advert", "Advert listing"), ("event", "Event registration"), ("membership", "Membership fee"), ("other", "Other")]
    GATEWAYS = [("mpesa", "M-Pesa"), ("mixx", "Mixx by Yas"), ("airtel", "Airtel Money"), ("selcom", "Selcom"), ("pesapal", "Pesapal"),
                ("dpo", "DPO"), ("card", "Visa / Mastercard"), ("paypal", "PayPal"), ("bank", "Bank transfer"), ("cash", "Cash")]
    STATUS = [("pending", "Pending"), ("completed", "Completed"), ("failed", "Failed"), ("refunded", "Refunded")]
    invoice_no = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    payer_name = models.CharField(max_length=100)
    payer_phone = models.CharField(max_length=20, blank=True)
    kind = models.CharField(max_length=12, choices=KINDS, default="premium")
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True)
    months = models.PositiveSmallIntegerField(default=1)
    description = models.CharField(max_length=160, blank=True)
    amount = models.PositiveIntegerField()
    gateway = models.CharField(max_length=10, choices=GATEWAYS, default="mpesa")
    reference = models.CharField(max_length=60, blank=True, help_text="Transaction / receipt number from the gateway")
    status = models.CharField(max_length=10, choices=STATUS, default="completed")
    created = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    class Meta: ordering = ["-created", "-pk"]
    def __str__(self): return f"{self.invoice_no} {self.payer_name} {self.amount}"

    def save(self, *args, **kwargs):
        if not self.invoice_no:
            year = self.created.year
            last = Payment.objects.filter(invoice_no__startswith=f"INV-{year}-").order_by("-invoice_no").values_list("invoice_no", flat=True).first()
            self.invoice_no = f"INV-{year}-{int(last.rsplit('-', 1)[1]) + 1 if last else 1:03d}"
        super().save(*args, **kwargs)

    def activate(self):
        """Give the payer's member profile the paid plan, extending any time they still have."""
        member = getattr(self.user, "member", None) if self.user_id else None
        if self.status != "completed" or self.kind != "premium" or not self.plan_id or member is None: return False
        start = max(member.premium_until or timezone.localdate(), timezone.localdate())
        y, m = divmod(start.month - 1 + self.months, 12)
        y, m = start.year + y, m + 1
        end = start.replace(year=y, month=m, day=min(start.day, calendar.monthrange(y, m)[1]))
        member.plan, member.premium_until = self.plan, end
        member.save(update_fields=["plan", "premium_until"])
        return True

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=120)
    body = models.TextField(max_length=2000, blank=True)
    link = models.CharField(max_length=200, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    class Meta: ordering = ["-created"]
    def __str__(self): return self.title

class MessageTemplate(models.Model):
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=140, blank=True)
    subject = models.CharField(max_length=150)
    body = models.TextField(help_text="You can use {name} for the member's name.")
    icon = models.CharField(max_length=30, default="mail")
    color = models.CharField(max_length=10, default="#2546a8")
    order = models.PositiveSmallIntegerField(default=0)
    class Meta: ordering = ["order", "pk"]
    def __str__(self): return self.name

class Broadcast(models.Model):
    CHANNELS = [("email", "Email"), ("inapp", "In-App Message"), ("notification", "Notification")]
    STATUS = [("draft", "Draft"), ("sent", "Sent")]
    channel = models.CharField(max_length=12, choices=CHANNELS)
    subject = models.CharField(max_length=150)
    body = models.TextField()
    filters = models.JSONField(default=dict, blank=True)
    recipients = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=6, choices=STATUS, default="draft")
    created = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    class Meta: ordering = ["-created"]
    def __str__(self): return self.subject
