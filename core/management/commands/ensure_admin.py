import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Create the first super admin from ADMIN_EMAIL / ADMIN_PASSWORD (and optional ADMIN_USERNAME) if it does not exist yet."
    def handle(self, *a, **k):
        email, password = os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD")
        if not (email and password):
            self.stdout.write("ADMIN_EMAIL / ADMIN_PASSWORD not set; skipping admin creation."); return
        User = get_user_model()
        username = os.getenv("ADMIN_USERNAME", "admin")
        if User.objects.filter(username=username).exists() or User.objects.filter(email__iexact=email).exists():
            self.stdout.write("Admin already exists; nothing to do."); return
        User.objects.create_superuser(username=username, email=email, password=password, first_name="Super", last_name="Admin")
        self.stdout.write(f"Created super admin '{username}'.")
