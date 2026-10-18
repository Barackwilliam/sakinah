"""Forgot password that works in practice: find the account by email, username or phone; send a branded email; and when email
cannot be delivered (not set up yet, provider down, or no email on the account) hand the request to the support team instead."""
import logging
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from .forms import FindAccountResetForm
from .models import SiteSetting, SupportTicket

log = logging.getLogger(__name__)

def reset_link(request, user):
    uid, token = urlsafe_base64_encode(force_bytes(user.pk)), default_token_generator.make_token(user)
    return request.build_absolute_uri(reverse("password_reset_confirm", args=[uid, token]))

def send_reset_email(request, user):
    site = SiteSetting.load()
    member = getattr(user, "member", None)
    ctx = {"name": member.name if member else (user.get_full_name() or user.username), "link": reset_link(request, user), "site": site,
           "username": user.get_username()}
    msg = EmailMultiAlternatives(f"{site.brand}: reset your password", render_to_string("registration/password_reset_email.txt", ctx),
                                 settings.DEFAULT_FROM_EMAIL, [user.email])
    msg.attach_alternative(render_to_string("registration/password_reset_email.html", ctx), "text/html")
    msg.send()

def ask_support(user, value, reason):
    """Leave a ticket so staff can send the member a reset link from the dashboard (e.g. on WhatsApp)."""
    if not SupportTicket.objects.filter(user=user, subject__startswith="Password reset help", status="open").exists():
        SupportTicket.objects.create(user=user, kind="contact", subject="Password reset help",
            message=f"{user.get_username()} asked to reset their password (typed: {value}). {reason} "
                    "Open Members Management, find this member and use \"Password reset link\" to send them a new link.")

def password_reset(request):
    form = FindAccountResetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        value = form.cleaned_data["email"]
        from django.core.cache import cache
        for user in form.get_users(value):
            if not cache.add(f"pw-reset:{user.pk}", 1, 120): continue   # at most one email every two minutes per account
            if not user.email:
                ask_support(user, value, "The account has no email address."); continue
            if not settings.EMAIL_LIVE and not settings.DEBUG:
                ask_support(user, value, "Email sending is not set up on the server yet."); continue
            try:
                send_reset_email(request, user)
            except Exception as e:
                log.error("Password reset email failed for %s: %s", user.pk, e)
                ask_support(user, value, "The email could not be sent.")
        # the next page reads the same whether or not an account matched, so nobody can probe which emails are registered
        return redirect("password_reset_done")
    return render(request, "registration/password_reset_form.html", {"form": form})

def password_reset_done(request):
    return render(request, "registration/password_reset_done.html", {"site": SiteSetting.load()})
