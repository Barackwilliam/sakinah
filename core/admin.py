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

@admin.register(models.Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["member", "reason", "reporter", "created", "resolved"]
    list_filter = ["resolved", "reason"]

class AdvertPhotoInline(admin.TabularInline):
    model = models.AdvertPhoto; extra = 1

@admin.register(models.Advert)
class AdvertAdmin(admin.ModelAdmin):
    list_display = ["title", "vendor", "category", "city", "price", "featured", "active", "views"]
    list_filter = ["category", "featured", "active", "city"]
    search_fields = ["title", "vendor__name"]
    prepopulated_fields = {"slug": ["title"]}
    inlines = [AdvertPhotoInline]

@admin.register(models.Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "verified", "member_since"]
    prepopulated_fields = {"slug": ["name"]}

@admin.register(models.Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ["name", "phone", "advert", "kind", "event_date", "created", "handled"]
    list_filter = ["handled", "kind"]

@admin.register(models.Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "author", "published", "featured", "views"]
    list_filter = ["category", "featured"]
    search_fields = ["title", "body"]
    prepopulated_fields = {"slug": ["title"]}

@admin.register(models.ArticleCategory)
class ArticleCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "order"]; prepopulated_fields = {"slug": ["name"]}

@admin.register(models.EventCategory)
class EventCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "order"]; prepopulated_fields = {"slug": ["name"]}

@admin.register(models.Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "date", "start_time", "city", "category"]
    list_filter = ["category", "city"]

for m in [models.SiteSetting, models.Plan, models.PremiumPerk, models.ServiceCategory, models.FeatureStrip, models.Like,
          models.AdvertReview, models.Wishlist, models.ArticleComment, models.EventRegistration, models.Shortlist]:
    admin.site.register(m)
