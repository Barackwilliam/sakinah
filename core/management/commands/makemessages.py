"""`makemessages` that also finds the short names this project uses for translatable text:
_l("...") for gettext_lazy and N("...") for gettext_noop (see core/form_labels.py, core/js_strings.py)."""
from django.core.management.commands.makemessages import Command as MakeMessages


class Command(MakeMessages):
    xgettext_options = MakeMessages.xgettext_options + ["--keyword=_l", "--keyword=N"]
