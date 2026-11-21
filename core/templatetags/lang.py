"""Language helpers for templates.

{% js_catalog %}   the few words the page scripts show (toasts, call status), in the current language
{{ text|tr }}      translate a word that comes from code or the database, e.g. a form label; unknown text is shown as it is
"""
import json
from functools import lru_cache
from django import template
from django.utils import translation
from django.utils.safestring import mark_safe

register = template.Library()


@lru_cache(maxsize=8)
def _catalog(lang):
    from core.js_strings import JS_STRINGS
    with translation.override(lang):
        pairs = {s: translation.gettext(s) for s in JS_STRINGS}
    return json.dumps({k: v for k, v in pairs.items() if k != v}, ensure_ascii=False).replace("</", "<\\/")


@register.simple_tag
def js_catalog():
    lang = translation.get_language() or "en"
    return mark_safe(f"<script>window.I18N={_catalog(lang)};window.gettext=function(s){{return I18N[s]||s}}</script>")


@register.filter
def tr(value):
    if not value: return value
    return translation.gettext(str(value))
