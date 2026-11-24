"""The "check your email" step: enter the 6-digit code (or click the link in the email), ask for a new code, or fix a mistyped address."""
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _, gettext_lazy as _l
from . import verify
from .models import EmailVerification
from .views import safe_next


class FixEmailForm(forms.Form):
    email = forms.EmailField(label=_l("Email address"))
    def __init__(self, *a, user=None, **kw):
        super().__init__(*a, **kw); self.user = user
    def clean_email(self):
        e = self.cleaned_data["email"].lower()
        if get_user_model().objects.filter(email__iexact=e).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError(_("An account with this email already exists."))
        return e


def _next(request):
    return safe_next(request) or verify.home_for(request.user)


@login_required
def verify_email(request):
    if not verify.needs_verifying(request.user): return redirect(_next(request))
    pending = EmailVerification.objects.filter(user=request.user, used=False).first()
    fix = FixEmailForm(request.POST if request.POST.get("action") == "fix" else None, user=request.user)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "code":
            result = verify.check_code(request.user, request.POST.get("code"))
            if result == "ok":
                messages.success(request, _("Your email is verified. Welcome to Sakinah!"))
                return redirect(_next(request))
            messages.error(request, {"wrong": _("That code is not right. Check the email and try again."),
                                     "locked": _("Too many wrong tries. We can send you a new code."),
                                     "expired": _("That code has expired. We can send you a new one.")}[result])
        elif action in ("resend", "fix"):
            if action == "fix" and not fix.is_valid():
                return render(request, "registration/verify.html", {"pending": pending, "fix": fix, "next": safe_next(request) or ""})
            if not cache.add(f"verify-resend:{request.user.pk}", 1, 60):
                messages.error(request, _("Please wait a minute before asking for another code."))
            else:
                email = fix.cleaned_data["email"] if action == "fix" else None
                if email:   # a typo at sign-up: send to the corrected address (saved once it is verified)
                    request.user.email = email; request.user.save(update_fields=["email"])
                verify.start(request, request.user, email)
                messages.success(request, _("We sent a new code to %(email)s.") % {"email": email or request.user.email})
        return redirect(request.get_full_path())
    return render(request, "registration/verify.html", {"pending": pending, "fix": fix, "next": safe_next(request) or ""})


def verify_email_link(request, token):
    """The button in the email. Works on any device, signed in or not."""
    v = EmailVerification.objects.select_related("user").filter(token=token).first()
    if v is None or v.used or v.expired:
        messages.error(request, _("This link has expired or was already used. Sign in to get a new code."))
        return redirect("login")
    verify.finish(v)
    messages.success(request, _("Your email is verified. Welcome to Sakinah!"))
    if request.user.is_authenticated and request.user.pk == v.user_id: return redirect(verify.home_for(request.user))
    return redirect("ad_login" if hasattr(v.user, "advertiser") and not hasattr(v.user, "member") else "login")
