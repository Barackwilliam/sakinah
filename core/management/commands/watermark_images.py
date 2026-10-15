from django.apps import apps
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import models
from core.images import process

class Command(BaseCommand):
    help = ("Stamp the watermark on pictures that were stored before watermarking was switched on. "
            "Safe to run again: pictures that already carry the watermark are skipped.")

    def handle(self, *a, **k):
        done = skipped = missing = 0
        seen = set()
        for model in apps.get_models():
            for f in [f for f in model._meta.get_fields() if isinstance(f, models.ImageField)]:
                for pk, name in model.objects.exclude(**{f.name: ""}).values_list("pk", f.name):
                    if not name or name in seen: continue
                    seen.add(name)
                    try:
                        with f.storage.open(name, "rb") as fh: data = fh.read()
                    except (FileNotFoundError, OSError):
                        missing += 1; continue
                    result = process(data, name, keep_format=True)
                    if not result:
                        skipped += 1; continue
                    new, _ = result
                    f.storage.delete(name)
                    saved = f.storage.save(name, ContentFile(new))   # already marked, so the storage stores it unchanged
                    if saved != name:
                        model.objects.filter(**{f.name: name}).update(**{f.name: saved})
                    done += 1
        self.stdout.write(f"Watermarked {done} pictures; {skipped} already marked or left as they are; {missing} missing files.")
