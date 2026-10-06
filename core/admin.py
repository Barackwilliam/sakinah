from django.contrib import admin
from . import models

class PhotoInline(admin.TabularInline):
    model = models.MemberPhoto; extra = 1

@admin.register(models.Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["name", "age", "gender", "city", "religion", "verified", "featured"]
    list_filter = ["gender", "religion", "verified", "featured", "city"]
    search_fields = ["name", "occupation", "user__username"]
    inlines = [PhotoInline]

@admin.register(models.Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["sender", "to", "created", "read"]

for m in [models.SiteSetting, models.Plan, models.PremiumPerk, models.ServiceCategory, models.Event, models.FeatureStrip, models.Like]:
    admin.site.register(m)
