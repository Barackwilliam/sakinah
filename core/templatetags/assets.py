"""{% asset 'css/main.css' %}: like {% static %}, but browsers always fetch the newest CSS/JS.

In production the static storage already puts a content hash in the file name. On a developer machine (DEBUG) files are served
without cache headers, so browsers may keep an old copy for hours; adding the file's modification time to the URL prevents that."""
import os
from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()

@register.simple_tag
def asset(path):
    url = static(path)
    if settings.DEBUG:
        found = finders.find(path)
        if found: url += f"?v={int(os.path.getmtime(found))}"
    return url
