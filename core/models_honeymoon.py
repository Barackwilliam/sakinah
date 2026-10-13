"""Honeymoon destinations and packages couples can browse and request to book."""
from django.conf import settings
from django.db import models
from django.urls import reverse

def lines(text):
    return [l.strip() for l in (text or "").splitlines() if l.strip()]

def icon_lines(text, default="star"):
    """'icon|text' lines -> [(icon, text)]; lines without an icon get the default one."""
    return [tuple(l.split("|", 1)) if "|" in l else (default, l) for l in lines(text)]

class Destination(models.Model):
    KINDS = [("beach", "Beach & Islands"), ("safari", "Safari & Nature"), ("mountains", "Mountains"), ("city", "Luxury Cities"),
             ("resort", "Luxury Resorts"), ("romantic", "Romantic Getaways")]
    REGIONS = [("tanzania", "Tanzania"), ("east-africa", "East Africa"), ("international", "International")]
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    country = models.CharField(max_length=60)
    kind = models.CharField("Destination type", max_length=12, choices=KINDS, default="beach")
    region = models.CharField(max_length=14, choices=REGIONS, default="tanzania")
    tagline = models.CharField(max_length=140, help_text="One line on the card, e.g. White sandy beaches, turquoise waters and luxury resorts.")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="honeymoon/", blank=True)
    from_price = models.PositiveIntegerField("From price (per couple)", default=0)
    days = models.PositiveSmallIntegerField("Typical days", default=5)
    nights = models.PositiveSmallIntegerField("Typical nights", default=4)
    features = models.TextField(blank=True, default="bed|Hotel\nfood|Meals\nmap|Tours",
                                help_text="Up to three short features on the card, one per line as icon|text. Icons: bed, food, map, safari, wave, city, dive, hike, villa.")
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=4.7)
    reviews = models.PositiveIntegerField("Number of reviews", default=0)
    featured = models.BooleanField(default=False, help_text="Show on the home page.")
    active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)
    class Meta: ordering = ["order", "name"]
    def __str__(self): return self.name
    def get_absolute_url(self): return reverse("hm_destination", args=[self.slug])
    @property
    def feature_list(self): return icon_lines(self.features)[:3]

class Package(models.Model):
    TYPES = [("beach", "Beach & Island"), ("resort", "Luxury Resort"), ("safari", "Safari & Beach"), ("city", "City & Culture"), ("all-inclusive", "All Inclusive")]
    BADGE_TONES = [("gold", "Gold"), ("green", "Green"), ("blue", "Blue"), ("pink", "Pink"), ("orange", "Orange"), ("purple", "Purple"), ("navy", "Navy")]
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name="packages")
    title = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    location = models.CharField(max_length=80, help_text="e.g. Zanzibar, Tanzania")
    package_type = models.CharField(max_length=14, choices=TYPES, default="beach")
    badge = models.CharField(max_length=30, blank=True, help_text="Ribbon on the photo, e.g. Best Seller, Luxury, All Inclusive.")
    badge_tone = models.CharField(max_length=8, choices=BADGE_TONES, default="gold")
    image = models.ImageField(upload_to="honeymoon/", blank=True)
    price = models.PositiveIntegerField("Price (per couple)", default=0)
    days = models.PositiveSmallIntegerField(default=5)
    nights = models.PositiveSmallIntegerField(default=4)
    stars = models.PositiveSmallIntegerField("Hotel category (stars)", default=5, choices=[(3, "3 Star"), (4, "4 Star"), (5, "5 Star")])
    stay = models.CharField("Accommodation", max_length=40, default="Luxury Resort")
    meals = models.CharField(max_length=40, default="All Meals", help_text="e.g. All Meals, Breakfast")
    meals_detail = models.CharField(max_length=60, blank=True, default="Breakfast, Lunch & Dinner")
    extra = models.CharField("Card extra", max_length=40, blank=True, default="Airport Transfer", help_text="Third feature on the card, e.g. Airport Transfer, Candle Dinner.")
    extra_icon = models.CharField(max_length=10, default="car", help_text="Icon for the extra: car, plane, map, dive, heart, villa, safari, wave, hike, gift.")
    flights = models.CharField("Flight option", max_length=60, default="Available on request")
    transfer = models.CharField("Airport transfer", max_length=60, default="Included")
    romance = models.CharField("Romantic activities", max_length=60, default="Included")
    overview = models.TextField(blank=True)
    highlights = models.TextField(blank=True, help_text="Package highlights, one per line as icon|text. Icons: palm, heart, dive, boat, camera, gift, safari, wine, spa, hike, city, star.")
    itinerary = models.TextField(blank=True, help_text="One day per line as Title|Details, e.g. Day 1 - Arrival|Airport pickup and welcome dinner.")
    inclusions = models.TextField(blank=True, help_text="What is included, one per line.")
    exclusions = models.TextField(blank=True, help_text="What is not included, one per line.")
    accommodation = models.TextField(blank=True, help_text="Where the couple stays.")
    activities = models.TextField(blank=True, help_text="Activities, one per line.")
    important_info = models.TextField("Important information", blank=True, help_text="One per line.")
    ideal_for = models.TextField(blank=True, default="heart|Honeymooners\npeople|Couples seeking romance\nsun|Beach lovers\ncamera|Adventure & exploration\nstar|Special occasions (Anniversary)",
                                 help_text="One per line as icon|text.")
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=4.7)
    reviews = models.PositiveIntegerField("Number of reviews", default=0)
    discount = models.BooleanField("Honeymoon discount", default=False)
    free_addons = models.BooleanField("Free add-ons", default=False)
    all_inclusive = models.BooleanField(default=False)
    featured = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["order", "-featured", "pk"]
    def __str__(self): return self.title
    def get_absolute_url(self): return reverse("hm_package", args=[self.slug])
    @property
    def highlight_list(self): return icon_lines(self.highlights)
    @property
    def itinerary_list(self): return [(l.split("|", 1) + [""])[:2] for l in lines(self.itinerary)]
    @property
    def inclusion_list(self): return lines(self.inclusions)
    @property
    def exclusion_list(self): return lines(self.exclusions)
    @property
    def activity_list(self): return lines(self.activities)
    @property
    def info_list(self): return lines(self.important_info)
    @property
    def ideal_list(self): return icon_lines(self.ideal_for, "heart")

class PackagePhoto(models.Model):
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="honeymoon/")
    caption = models.CharField(max_length=80, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    class Meta: ordering = ["order", "pk"]
    def __str__(self): return self.caption or f"Photo of {self.package}"

class Booking(models.Model):
    STATUS = [("new", "New"), ("contacted", "Contacted"), ("confirmed", "Confirmed"), ("cancelled", "Cancelled")]
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="bookings")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="honeymoon_bookings")
    name = models.CharField(max_length=80)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    travel_date = models.DateField(null=True, blank=True)
    couples = models.PositiveSmallIntegerField(default=1)
    message = models.TextField(max_length=1000, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default="new")
    created = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["-created"]
    def __str__(self): return f"{self.name} - {self.package}"
    @property
    def total(self): return self.package.price * self.couples

class PackageReview(models.Model):
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name="member_reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="package_reviews")
    rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(max_length=1000, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created"]
        constraints = [models.UniqueConstraint(fields=["package", "user"], name="unique_package_review")]

class HoneymoonSave(models.Model):
    """A heart on a destination or package card."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="honeymoon_saves")
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, null=True, blank=True, related_name="saves")
    package = models.ForeignKey(Package, on_delete=models.CASCADE, null=True, blank=True, related_name="saves")
    created = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "destination"], name="unique_dest_save"),
                       models.UniqueConstraint(fields=["user", "package"], name="unique_pkg_save")]
