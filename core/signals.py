"""Staff accounts get the "Administrators" group, so every admin dashboard link works for them (no 403 pages).
Super admins already have every permission; creating or editing user accounts and roles stays with super admins, so staff cannot raise their own access."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

GROUP = "Administrators"

def admin_group():
    group, _ = Group.objects.get_or_create(name=GROUP)
    perms = Permission.objects.filter(content_type__app_label="core") | Permission.objects.filter(
        content_type__app_label="auth", codename__in=["view_user", "view_group"]) | Permission.objects.filter(
        content_type__app_label="admin", codename="view_logentry")
    group.permissions.set(perms)
    return group

@receiver(post_migrate)
def sync_admin_group(sender, **kwargs):
    if sender.name != "core": return
    group = admin_group()
    for u in get_user_model().objects.filter(is_staff=True, is_superuser=False).exclude(groups=group):
        u.groups.add(group)

@receiver(post_save, sender=get_user_model())
def staff_joins_admin_group(sender, instance, **kwargs):
    if instance.is_staff and not instance.is_superuser and not instance.groups.filter(name=GROUP).exists():
        instance.groups.add(admin_group())
