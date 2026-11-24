"""Advert packages run for days (7, 15, 30) instead of months, the three starter packages become Standard, Platinum
and Premium Featured, and adverts are now for every kind of business, so general categories are added."""
from django.db import migrations, models
from django.utils.text import slugify


def forwards(apps, schema_editor):
    from core.seed_data import AD_PACKAGES, GENERAL_CATEGORIES
    AdPackage, ServiceCategory = apps.get_model("core", "AdPackage"), apps.get_model("core", "ServiceCategory")
    for p in AdPackage.objects.all(): p.days = p.days * 30; p.save(update_fields=["days"])   # a month was 30 days
    old = {"starter": 0, "featured": 1, "spotlight": 2}            # the starter set: renamed in place, so orders keep their package
    for slug, i in old.items():
        slug2, name, tagline, price, days, photos, featured, home, popular, features = AD_PACKAGES[i]
        p = AdPackage.objects.filter(slug=slug).first()
        if p is None and not AdPackage.objects.filter(slug=slug2).exists(): p = AdPackage(slug=slug2)
        if p is None: continue
        p.slug, p.name, p.tagline, p.price, p.days, p.max_photos = slug2, name, tagline, price, days, photos
        p.featured, p.home_page, p.popular, p.features, p.order, p.active = featured, home, popular, features, i, True
        p.save()
    start = ServiceCategory.objects.count()
    for i, (name, blurb) in enumerate(GENERAL_CATEGORIES):
        ServiceCategory.objects.get_or_create(slug=slugify(name), defaults=dict(name=name, blurb=blurb, order=start + i))


class Migration(migrations.Migration):
    dependencies = [("core", "0027_advertiser")]
    operations = [
        migrations.RenameField("adpackage", "months", "days"),
        migrations.AlterField("adpackage", "days", models.PositiveSmallIntegerField(
            default=7, help_text="How many days the advert is featured on the site, e.g. 7, 15 or 30.")),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
