import re
from pathlib import Path
from django.apps import apps
from django.conf import settings
from django.core.files import File
from django.core.files.storage import FileSystemStorage
from django.core.management.base import BaseCommand
from django.db import models

SUFFIX = re.compile(r"_[A-Za-z0-9]{7}(?=\.[^.]+$)")   # Django adds "_AbC1234" when a file name is already taken

class Command(BaseCommand):
    help = ("Put back starter images that the database still points to but that are missing on disk. "
            "Render's disk is wiped on every deploy, so without Supabase Storage the seeded pictures would otherwise break. "
            "Files people uploaded themselves cannot be recovered this way; use Supabase Storage for those.")

    def handle(self, *a, **k):
        root = Path(settings.BASE_DIR) / "seed_images"
        index = {}
        # newer image sets win when two folders hold the same file name
        for folder in sorted({p.parent for p in root.rglob("*") if p.is_file()}, key=lambda d: str(d)):
            for p in folder.iterdir():
                if p.is_file(): index[p.name.lower()] = p
        restored = missing = checked = 0
        for model in apps.get_models():
            fields = [f for f in model._meta.get_fields() if isinstance(f, models.FileField)]
            if not fields: continue
            for f in fields:
                if not isinstance(f.storage, FileSystemStorage): continue
                for pk, name in model.objects.exclude(**{f.name: ""}).values_list("pk", f.name):
                    checked += 1
                    if not name or f.storage.exists(name): continue
                    base = Path(name).name
                    src = index.get(base.lower()) or index.get(SUFFIX.sub("", base).lower())
                    if src is None:
                        missing += 1; continue
                    with open(src, "rb") as fh: f.storage.save(name, File(fh))
                    restored += 1
        self.stdout.write(f"Checked {checked} files: restored {restored}, {missing} still missing (uploaded by people, not starter images).")
