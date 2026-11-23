"""The site's four languages: choosing one, remembering it, and carrying it to members' other devices.

A visitor's choice lives in Django's language cookie (LocaleMiddleware reads it). A signed-in member's choice is also
saved on their profile (Member.ui_language), so the site opens in their language on a new phone or after the cookie is gone.
"""
from django.conf import settings
from django.utils import translation
from django.views.decorators.http import require_POST
from django.middleware.locale import LocaleMiddleware
from django.views.i18n import set_language as django_set_language

CODES = {code for code, _name in settings.LANGUAGES}


def remember(response, code):
    """Put the language in the cookie LocaleMiddleware reads on every request."""
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, code, max_age=settings.LANGUAGE_COOKIE_AGE,
                        path=settings.LANGUAGE_COOKIE_PATH, domain=settings.LANGUAGE_COOKIE_DOMAIN,
                        secure=settings.LANGUAGE_COOKIE_SECURE, httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
                        samesite=settings.LANGUAGE_COOKIE_SAMESITE)
    return response


def save_for_member(user, code):
    if code in CODES and user.is_authenticated:
        from .models import Member
        Member.objects.filter(user=user).exclude(ui_language=code).update(ui_language=code)


class SiteLocaleMiddleware(LocaleMiddleware):
    """The language a visitor chose (cookie), otherwise the site's own language (Kiswahili) - never a guess from the browser."""
    def process_request(self, request):
        code = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if code not in CODES: code = getattr(settings, "SITE_LANGUAGE", "") or settings.LANGUAGE_CODE
        translation.activate(code)
        request.LANGUAGE_CODE = translation.get_language()


@require_POST
def set_language(request):
    """The language menu. Django's own view sets the cookie and goes back to the page; this also saves it on the profile."""
    response = django_set_language(request)
    save_for_member(request.user, request.POST.get("language"))
    return response


class MemberLanguageMiddleware:
    """A member signing in on a device that has no language cookie gets the language saved on their profile."""
    def __init__(self, get_response): self.get_response = get_response

    def __call__(self, request):
        code = None
        if (settings.LANGUAGE_COOKIE_NAME not in request.COOKIES and request.user.is_authenticated
                and not request.session.get("lang_checked")):
            from .models import Member
            code = Member.objects.filter(user=request.user).values_list("ui_language", flat=True).first()
            request.session["lang_checked"] = True   # one lookup per sign-in, even for members who never chose
            if code in CODES:
                if code != request.LANGUAGE_CODE: translation.activate(code); request.LANGUAGE_CODE = code
            else:
                code = None   # not chosen: the site's language stands
        response = self.get_response(request)
        if code: remember(response, code)
        return response
