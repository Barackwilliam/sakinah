from django import template
from django.utils.timesince import timesince

register = template.Library()

@register.filter
def ago(value):
    """'2 hours ago' / '3 days ago' - only the largest unit of timesince."""
    if not value: return ""
    import re
    first = re.split("[,،]", timesince(value))[0].replace("\xa0", " ").strip()   # Arabic uses its own comma
    from django.utils.translation import gettext
    return gettext("Just now") if first.startswith("0 ") else gettext("%(time)s ago") % {"time": first}
