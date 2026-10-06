from django.contrib import admin
from . import models
for m in [models.SiteSetting, models.Plan, models.PremiumPerk, models.Member, models.ServiceCategory, models.Event, models.FeatureStrip]:
    admin.site.register(m)
