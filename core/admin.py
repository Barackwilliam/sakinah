from django.contrib import admin
from . import models
for m in [models.SiteSetting, models.Plan, models.PremiumPerk, models.Member, models.ServiceCategory, models.Event, models.FeatureStrip, models.Like]:
    admin.site.register(m)
