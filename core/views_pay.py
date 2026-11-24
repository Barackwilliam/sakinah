"""Where Pesapal sends the payer back (callback) and where its servers report a payment change (IPN)."""
import logging
from django.contrib import messages
from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from . import pesapal
from .models import Payment, SiteSetting

log = logging.getLogger(__name__)


def after_payment_url(p):
    if p.kind == "advert" and p.ad_order_id: return reverse("ad_detail", args=[p.ad_order.token])
    if p.kind == "banner" and p.banner_order_id: return reverse("ad_banner", args=[p.banner_order.token])
    if p.kind == "premium": return reverse("m_membership") + "?tab=mine"
    return reverse("home")


@xframe_options_sameorigin       # Pesapal sends the payer back inside our checkout page's frame
def callback(request):
    p = Payment.objects.filter(tracking_id=request.GET.get("OrderTrackingId", "")[:64]).exclude(tracking_id="").first()
    if p is None:
        messages.error(request, _("We could not find that payment. If money left your account, please contact us."))
        return redirect("home")
    try:
        status = pesapal.refresh(p, request)
    except pesapal.PesapalError as e:
        log.warning("Pesapal status check failed for %s: %s", p.invoice_no, e); status = p.status
    if status == "completed":
        messages.success(request, _("Payment received, thank you! It is confirmed and already active."))
    elif status == "failed":
        messages.error(request, _("The payment did not go through. You can try again."))
    else:
        messages.info(request, _("Your payment is being processed. This page updates as soon as Pesapal confirms it."))
    # inside the checkout page's frame: take the whole window to the next page, not just the frame
    return render(request, "payments/return.html", {"next": after_payment_url(p)})


@csrf_exempt
def ipn(request):
    """Pesapal calls this from its servers. We check the status with Pesapal ourselves before believing anything."""
    q = request.GET if request.method == "GET" else request.POST
    tracking, ref = q.get("OrderTrackingId", "")[:64], q.get("OrderMerchantReference", "")
    p = Payment.objects.filter(tracking_id=tracking).exclude(tracking_id="").first() if tracking else None
    ok = 500
    if p is not None:
        try:
            pesapal.refresh(p, request); ok = 200
        except pesapal.PesapalError as e:
            log.warning("Pesapal IPN check failed for %s: %s", p.invoice_no, e)
    return JsonResponse({"orderNotificationType": q.get("OrderNotificationType", "IPNCHANGE"), "orderTrackingId": tracking,
                         "orderMerchantReference": ref, "status": ok})


def _item(p):
    """What the payment is for, for the checkout page: (title, detail, back link)."""
    from django.utils.translation import gettext as _g, ngettext
    if p.kind == "premium" and p.plan_id:
        months = p.months or 1
        return (p.plan.name, ngettext("%(n)d month of membership", "%(n)d months of membership", months) % {"n": months},
                reverse("m_membership"))
    if p.kind == "advert" and p.ad_order_id:
        o = p.ad_order
        return (o.title, f"{o.package.name} · " + ngettext("%(n)d day", "%(n)d days", o.package.days) % {"n": o.package.days},
                reverse("ad_detail", args=[o.token]))
    if p.kind == "banner" and p.banner_order_id:
        b = p.banner_order
        return (b.business_name, f"{b.slot.name} · " + ngettext("%(n)d day", "%(n)d days", b.slot.days) % {"n": b.slot.days},
                reverse("ad_banner", args=[b.token]))
    return (p.get_kind_display(), p.description, reverse("home"))


def _mine(request, invoice):
    p = Payment.objects.select_related("plan", "ad_order__package", "banner_order__slot").filter(invoice_no=invoice).first()
    if p is None or not request.user.is_authenticated or (p.user_id != request.user.pk and not request.user.is_staff): raise Http404
    return p


def pay(request, invoice):
    """Our checkout page: a summary of what is being paid for, with Pesapal's payment form opened inside it."""
    if not request.user.is_authenticated: return redirect(f"{reverse('login')}?next={request.path}")
    p = _mine(request, invoice)
    if p.status != "pending" or not p.checkout_url: return redirect(after_payment_url(p))
    title, detail, back = _item(p)
    return render(request, "payments/checkout.html", {"p": p, "title": title, "detail": detail, "back": back,
                                                      "site": SiteSetting.load(), "status_url": reverse("pay_status", args=[p.invoice_no])})


def pay_status(request, invoice):
    """Polled by the checkout page: has Pesapal confirmed the payment yet? Asks Pesapal at most every few seconds."""
    p = _mine(request, invoice)
    if p.status == "pending" and p.tracking_id and cache.add(f"pay-check:{p.pk}", 1, 6):
        try: pesapal.refresh(p, request)
        except pesapal.PesapalError as e: log.warning("Pesapal status check failed for %s: %s", p.invoice_no, e)
    done = p.status in ("completed", "failed")
    if done and p.status == "completed": messages.success(request, _("Payment received, thank you! It is confirmed and already active."))
    elif done: messages.error(request, _("The payment did not go through. You can try again."))
    return JsonResponse({"status": p.status, "next": after_payment_url(p) if done else ""})
