import os
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = ("Create the client's Super Admin from ADMIN_EMAIL / ADMIN_PASSWORD (and optional ADMIN_USERNAME) if it does not exist yet. "
            "This account manages everything from /dashboard/ but cannot open the developer-only Django admin; "
            "create your own developer account with `python manage.py createsuperuser`.")
    def handle(self, *a, **k):
        Group.objects.get_or_create(name="Super Admins")
        email, password = os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD")
        if not (email and password):
            self.stdout.write("ADMIN_EMAIL / ADMIN_PASSWORD not set; skipping admin creation."); return
        User = get_user_model()
        username = os.getenv("ADMIN_USERNAME", "admin")
        if User.objects.filter(username=username).exists() or User.objects.filter(email__iexact=email).exists():
            self.stdout.write("Admin already exists; nothing to do."); return
        user = User.objects.create_user(username=username, email=email, password=password, first_name="Super", last_name="Admin", is_staff=True)
        user.groups.add(Group.objects.get(name="Super Admins"))
        self.stdout.write(f"Created Super Admin '{username}' for the dashboard.")
