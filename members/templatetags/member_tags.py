from django import template
from django.utils.timesince import timesince

register = template.Library()

@register.filter
def ago(value):
    """'2 hours ago' / '3 days ago' - only the largest unit of timesince."""
    if not value: return ""
    first = timesince(value).split(",")[0].replace("\xa0", " ")
    return "Just now" if first.startswith("0 ") else f"{first} ago"
