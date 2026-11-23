"""Email verification: when someone signs up (or changes their email) we send a 6-digit code and a one-click link.
Until one of them is used, the account can't go further than the "check your email" page (EmailVerifiedMiddleware).

If the server can't send email at all (no BREVO_API_KEY / RESEND_API_KEY / EMAIL_HOST), verification is skipped,
because nobody could ever finish signing up."""
import logging
import secrets
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 5


def required():
    return bool(getattr(settings, "EMAIL_LIVE", False))


def mark(user, verified):
    """Members and advertisers both carry the flag; set it on whichever this account is."""
    from .models import Advertiser, Member
    Member.objects.filter(user=user).update(email_verified=verified)
    Advertiser.objects.filter(user=user).update(email_verified=verified)


def home_for(user):
    """Where an account goes once its email is verified: advertisers to their dashboard, members to their profile."""
    from .models_ads import is_advertiser
    return "ad_dashboard" if is_advertiser(user) else "m_profile_edit"


def start(request, user, email=None):
    """Ask the member to prove the email is theirs. Returns True when an email was sent (verification is on)."""
    from .models import EmailVerification, SiteSetting
    email = (email or user.email or "").strip()
    if not required() or not email:
        mark(user, True)
        return False
    mark(user, False)
    EmailVerification.objects.filter(user=user, used=False).update(used=True)   # only the newest code works
    code = f"{secrets.randbelow(1_000_000):06d}"
    v = EmailVerification.objects.create(user=user, email=email, code_hash=make_password(code), token=secrets.token_urlsafe(24))
    site, who = SiteSetting.load(), getattr(user, "member", None) or getattr(user, "advertiser", None)
    ctx = {"name": who.first_name if who else user.get_username(), "code": code, "site": site,
           "link": request.build_absolute_uri(reverse("verify_email_link", args=[v.token]))}
    msg = EmailMultiAlternatives(f"{code} - {site.brand}", render_to_string("registration/verify_email.txt", ctx), settings.DEFAULT_FROM_EMAIL, [email])
    msg.attach_alternative(render_to_string("registration/verify_email.html", ctx), "text/html")
    try:
        msg.send()
    except Exception as e:   # a mail outage must not lock the member out
        log.error("Verification email to user %s failed: %s", user.pk, e)
        mark(user, True)
        return False
    return True


def check_code(user, code):
    """'ok', 'wrong', 'expired' or 'locked'."""
    from .models import EmailVerification
    v = EmailVerification.objects.filter(user=user, used=False).first()
    if v is None or v.expired: return "expired"
    if v.attempts >= MAX_ATTEMPTS: return "locked"
    if not check_password((code or "").strip(), v.code_hash):
        EmailVerification.objects.filter(pk=v.pk).update(attempts=v.attempts + 1)
        return "locked" if v.attempts + 1 >= MAX_ATTEMPTS else "wrong"
    finish(v); return "ok"


def finish(v):
    v.used = True; v.save(update_fields=["used"])
    if v.user.email != v.email:
        v.user.email = v.email; v.user.save(update_fields=["email"])
    mark(v.user, True)


def needs_verifying(user):
    if not user.is_authenticated or user.is_staff: return False
    return any(who is not None and not who.email_verified
               for who in (getattr(user, "member", None), getattr(user, "advertiser", None)))


class EmailVerifiedMiddleware:
    """An account whose email isn't verified yet can browse the public site, but not its account, chats or profiles."""
    BLOCKED = ("/account/", "/messages/", "/members/", "/likes/", "/notifications/", "/profile/", "/advertise/dashboard/")
    OPEN = ("/account/verify-email/", "/account/password-reset/", "/account/reset/")

    def __init__(self, get_response): self.get_response = get_response

    def __call__(self, request):
        p = request.path
        if p.startswith(self.BLOCKED) and not p.startswith(self.OPEN) and needs_verifying(request.user):
            return redirect(reverse("verify_email") + f"?next={p}")
        return self.get_response(request)
