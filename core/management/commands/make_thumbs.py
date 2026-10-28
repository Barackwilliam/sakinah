"""Build the small copy of every member photo that does not have one yet.

Cards, avatars and conversation rows show a photo the size of a stamp; without this they would
each fetch the full-size picture instead. Safe to run again: it skips the ones already done.
"""
from django.core.management.base import BaseCommand
from core.models import Member


class Command(BaseCommand):
    help = "Make the small copy of each member photo used by cards and avatars"

    def handle(self, *a, **k):
        made = skipped = 0
        for m in Member.objects.exclude(photo="").only("pk", "photo", "thumb"):
            before = m.thumb.name
            m.make_thumb()
            if m.thumb.name != before: made += 1
            else: skipped += 1
        self.stdout.write(f"Thumbnails: {made} made, {skipped} already there.")
