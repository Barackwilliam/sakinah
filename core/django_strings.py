"""Words from Django itself that its Kiswahili translation leaves in English (e.g. "3 months" in "3 months ago").

Listed here so `makemessages` keeps them in our catalogs, where locale/sw fills them in. Never imported."""
from django.utils.translation import ngettext_lazy

TIMESINCE = [
    ngettext_lazy("%(num)d year", "%(num)d years", "num"),
    ngettext_lazy("%(num)d month", "%(num)d months", "num"),
    ngettext_lazy("%(num)d week", "%(num)d weeks", "num"),
    ngettext_lazy("%(num)d day", "%(num)d days", "num"),
    ngettext_lazy("%(num)d hour", "%(num)d hours", "num"),
    ngettext_lazy("%(num)d minute", "%(num)d minutes", "num"),
]
