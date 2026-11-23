"""Where Pesapal sends the payer back (callback) and where its servers report a payment change (IPN)."""
import logging
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from . import pesapal
from .models import Payment

log = logging.getLogger(__name__)


def after_payment_url(p):
    if p.kind == "advert" and p.ad_order_id: return reverse("m_ad", args=[p.ad_order.token])
    if p.kind == "premium": return reverse("m_membership") + "?tab=mine"
    return reverse("home")


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
    return redirect(after_payment_url(p))


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
