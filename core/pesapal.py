"""Pesapal (API 3.0, live) for every payment on the site: membership plans and adverts.

How a payment goes:
1. We create a pending Payment and ask Pesapal for a checkout page (SubmitOrderRequest); the payer is sent there.
2. The payer pays with M-Pesa, Airtel Money, Mixx by Yas, a card, ... on Pesapal's page.
3. Pesapal sends the payer back to our callback URL, and also calls our IPN URL from its own servers.
4. Either way we never trust the visit itself: we ask Pesapal for the transaction status, and only a "Completed"
   answer marks the payment completed, which activates the plan or publishes the advert (once, however often we are told).

Settings (environment variables on Render): PESAPAL_CONSUMER_KEY and PESAPAL_CONSUMER_SECRET from the Pesapal
merchant dashboard. Without them the site falls back to the manual "enter the transaction reference" form.
"""
import json
import logging
import urllib.request
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

log = logging.getLogger(__name__)
LIVE_URL = "https://pay.pesapal.com/v3/api"
SANDBOX_URL = "https://cybqa.pesapal.com/pesapalv3/api"


class PesapalError(Exception):
    pass


def configured():
    return bool(getattr(settings, "PESAPAL_CONSUMER_KEY", "") and getattr(settings, "PESAPAL_CONSUMER_SECRET", ""))


def _base():
    return SANDBOX_URL if getattr(settings, "PESAPAL_SANDBOX", False) else LIVE_URL


def _call(method, path, data=None, token=None):
    """One JSON request to Pesapal. Kept in one place so tests can replace it."""
    req = urllib.request.Request(_base() + path, method=method, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Accept": "application/json", "Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read().decode() or "{}")
    except Exception as e:
        raise PesapalError(f"Pesapal could not be reached: {e}") from e
    err = body.get("error") if isinstance(body, dict) else None
    if err and (err.get("code") or err.get("message")):
        raise PesapalError(err.get("message") or err.get("code"))
    return body


def token():
    """Access tokens last 5 minutes; keep one for 4."""
    t = cache.get("pesapal-token")
    if not t:
        body = _call("POST", "/Auth/RequestToken", {"consumer_key": settings.PESAPAL_CONSUMER_KEY,
                                                    "consumer_secret": settings.PESAPAL_CONSUMER_SECRET})
        t = body.get("token")
        if not t: raise PesapalError("Pesapal did not return an access token.")
        cache.set("pesapal-token", t, 240)
    return t


def ipn_id(request):
    """Pesapal needs our IPN URL registered once; the id it returns goes with every order. Saved in Site Settings."""
    from .models import SiteSetting
    site = SiteSetting.load()
    url = request.build_absolute_uri(reverse("pesapal_ipn"))
    if site.pesapal_ipn_id and site.pesapal_ipn_url == url:
        return site.pesapal_ipn_id
    body = _call("POST", "/URLSetup/RegisterIPN", {"url": url, "ipn_notification_type": "GET"}, token())
    if not body.get("ipn_id"): raise PesapalError("Pesapal did not return an IPN id.")
    obj = SiteSetting.objects.first() or SiteSetting()
    obj.pesapal_ipn_id, obj.pesapal_ipn_url = body["ipn_id"], url
    obj.save()
    return body["ipn_id"]


def checkout(payment, request, email="", phone="", name=""):
    """Ask Pesapal for a checkout page for this pending payment; returns the URL to send the payer to."""
    first, _, last = (name or payment.payer_name or "Sakinah").partition(" ")
    order = {
        "id": payment.invoice_no,                      # our reference; unique, as Pesapal requires
        "currency": "TZS",
        "amount": payment.amount,
        "description": (payment.description or payment.get_kind_display())[:100],
        "callback_url": request.build_absolute_uri(reverse("pesapal_callback")),
        "notification_id": ipn_id(request),
        "billing_address": {"email_address": email or "", "phone_number": phone or payment.payer_phone or "",
                            "country_code": "TZ", "first_name": first[:50], "last_name": (last or first)[:50]},
    }
    body = _call("POST", "/Transactions/SubmitOrderRequest", order, token())
    if not body.get("redirect_url") or not body.get("order_tracking_id"):
        raise PesapalError("Pesapal did not return a checkout page.")
    payment.tracking_id = body["order_tracking_id"]
    payment.save(update_fields=["tracking_id"])
    return body["redirect_url"]


def refresh(payment, request=None):
    """Ask Pesapal how this payment stands and act on the answer. Safe to call any number of times."""
    if not payment.tracking_id or payment.status != "pending":
        return payment.status
    body = _call("GET", f"/Transactions/GetTransactionStatus?orderTrackingId={payment.tracking_id}", token=token())
    try: code = int(body.get("status_code"))
    except (TypeError, ValueError): code = None
    desc = (body.get("payment_status_description") or "").lower()
    if code == 1 or desc == "completed":
        complete(payment, request, reference=body.get("confirmation_code") or "", method=body.get("payment_method") or "")
    elif code in (2, 3) or desc in ("failed", "reversed", "invalid"):
        from .models import Payment
        Payment.objects.filter(pk=payment.pk, status="pending").update(status="failed")
    payment.refresh_from_db()
    return payment.status


def complete(payment, request=None, reference="", method=""):
    """Mark a payment completed and deliver what was bought - exactly once, even if Pesapal tells us twice."""
    from .models import Notification, Payment
    with transaction.atomic():
        done = Payment.objects.filter(pk=payment.pk, status="pending").update(status="completed", reference=(reference or payment.reference)[:60],
                                                                             pay_method=method[:40], created=payment.created)
        if not done: return False
        payment.refresh_from_db()
        if payment.kind == "advert" and payment.ad_order_id:
            payment.ad_order.publish(request)
        elif payment.kind == "banner" and payment.banner_order_id:
            payment.banner_order.paid(request)
        elif payment.kind == "premium" and payment.activate() and payment.user_id:
            m = payment.user.member
            Notification.objects.create(user=payment.user, title=f"{payment.plan.name} plan activated", link=reverse("m_membership"),
                                        body=f"Thank you! Your {payment.plan.name} plan is active until {m.premium_until:%d %b %Y}.")
    log.info("Pesapal payment %s completed at %s", payment.invoice_no, timezone.now())
    return True
