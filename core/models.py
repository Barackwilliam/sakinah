from django.conf import settings
from django.db import models
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
    class Meta: verbose_name = "Site setting"
    @classmethod
    def load(cls):
        return cls.objects.first() or cls()
    def __str__(self): return self.brand

class Plan(models.Model):
    name = models.CharField(max_length=50)
    price = models.PositiveIntegerField(default=0)
    order = models.PositiveSmallIntegerField(default=0)
    class Meta: ordering = ["order"]
    def __str__(self): return self.name

class PremiumPerk(models.Model):
    text = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=0)
    class Meta: ordering = ["order"]
    def __str__(self): return self.text

class Member(models.Model):
    GENDER = [("F", "Woman"), ("M", "Man")]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="member")
    name = models.CharField(max_length=80)
    age = models.PositiveSmallIntegerField()
    gender = models.CharField(max_length=1, choices=GENDER)
    city = models.CharField(max_length=60)
    occupation = models.CharField(max_length=80)
    intention = models.CharField(max_length=60, default="Marriage-oriented")
    religion = models.CharField(max_length=30, default="Islam")
    bio = models.TextField(max_length=600, blank=True)
    photo = models.ImageField(upload_to="members/", blank=True)
    verified = models.BooleanField(default=False)
    featured = models.BooleanField(default=False)
    compatibility = models.PositiveSmallIntegerField(default=80)
    joined = models.DateTimeField(default=timezone.now)
    class Meta: ordering = ["-featured", "-verified", "-joined"]
    def __str__(self): return f"{self.name}, {self.age}"

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

class Event(models.Model):
    title = models.CharField(max_length=120)
    date = models.DateField()
    city = models.CharField(max_length=60)
    description = models.CharField(max_length=200, blank=True)
    image = models.ImageField(upload_to="events/", blank=True)
    attendees = models.PositiveIntegerField(default=0)
    class Meta: ordering = ["date"]
    def __str__(self): return self.title

class FeatureStrip(models.Model):
    """Bottom icon strip on home."""
    title = models.CharField(max_length=50)
    text = models.CharField(max_length=80)
    icon = models.CharField(max_length=30, default="heart")
    order = models.PositiveSmallIntegerField(default=0)
    class Meta: ordering = ["order"]
