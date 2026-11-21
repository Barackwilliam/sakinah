"""Write core/form_labels.py: the form labels Django makes from field names, so `makemessages` can see them.

Labels given in code are already marked for translation; the ones Django builds itself (field "body_type" becomes
"Body type") are not. Run this after adding model or form fields, then `makemessages`:

    python manage.py form_labels
"""
import importlib, inspect
from pathlib import Path
from django import forms
from django.conf import settings
from django.core.management.base import BaseCommand
from django.forms.utils import pretty_name
from django.utils.functional import Promise

MODULES = ["core.forms", "members.forms", "dashboard.forms", "dashboard.views_manage", "core.faces", "core.views_password"]


def plain_texts(form_class):
    fields = dict(getattr(form_class, "base_fields", {}))
    try: fields.update(form_class().fields)   # labels set in __init__
    except Exception: pass
    for name, f in fields.items():
        for text in (f.label if f.label is not None else pretty_name(name), f.help_text):
            if text and not isinstance(text, Promise) and any(c.isalpha() for c in str(text)):
                yield str(text)


class Command(BaseCommand):
    help = "List the auto-made form labels in core/form_labels.py so they can be translated."

    def handle(self, *args, **opts):
        classes = set()
        for m in MODULES:
            for c in vars(importlib.import_module(m)).values():
                if inspect.isclass(c) and issubclass(c, forms.BaseForm) and c.__module__ == m: classes.add(c)
        from dashboard.resources import REGISTRY
        classes |= {r.form for r in REGISTRY.values() if r.form}
        texts = sorted({t for c in classes for t in plain_texts(c)})
        lines = ['"""Form labels Django makes from field names (e.g. "Body type"), listed so they can be translated.', "",
                 "Made by `python manage.py form_labels`; templates show them with {{ f.label|tr }}. Do not edit by hand.\"\"\"",
                 "from django.utils.translation import gettext_noop as N", "", "LABELS = ["]
        lines += [f"    N({t!r})," for t in texts] + ["]"]
        Path(settings.BASE_DIR, "core", "form_labels.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.stdout.write(f"{len(texts)} labels written to core/form_labels.py")
