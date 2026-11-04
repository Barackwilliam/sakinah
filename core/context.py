from functools import lru_cache
from urllib.parse import urlsplit
from django.conf import settings
from django.utils.functional import SimpleLazyObject
from .forms import LoginForm, SignupForm
from .models import Message, SiteSetting

def _media_host():
    """Where photos are served from, when that is somewhere else (Supabase Storage).

    The page tells the browser to open that connection early, so the first photo does not
    wait on a fresh DNS lookup and TLS handshake.
    """
    url = getattr(settings, "MEDIA_URL", "") or ""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""

MEDIA_HOST = _media_host()

@lru_cache(maxsize=8)
def _sprite(name):
    """The icon sprite's URL. One cached file beats repeating 24KB of SVG inside every page."""
    from .templatetags.assets import asset
    try: return asset(name)
    except Exception: return f"{settings.STATIC_URL}{name}"

def site(request):
    ctx = {"site": SiteSetting.load(), "media_host": MEDIA_HOST,
           "icons": _sprite("icons.svg"), "micons": _sprite("micons.svg"),
           "current": request.resolver_match.url_name if request.resolver_match else ""}
    user = getattr(request, "user", None)
    if user is None: return ctx
    if user.is_authenticated:
        # counted only if a template actually shows them (the dashboards supply their own)
        ctx["unread"] = SimpleLazyObject(lambda: Message.objects.filter(to__user=user, read=False).count())
        ctx["n_notes"] = SimpleLazyObject(lambda: user.notifications.filter(read=False).count())
    else:
        ctx["modal_login"] = SimpleLazyObject(lambda: LoginForm(request, auto_id="li_%s"))
        ctx["modal_signup"] = SimpleLazyObject(lambda: SignupForm(auto_id="su_%s"))
    return ctx
