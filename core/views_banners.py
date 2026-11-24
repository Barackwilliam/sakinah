"""Banner adverts in the advertiser dashboard (book a place, pay, follow views and clicks) and the click counter."""
import logging
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import F
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from . import pesapal
from .forms_ads import AdPaymentForm, BannerOrderForm
from .models import BannerOrder, BannerSlot, Notification, Payment
from .views_ads import _page, advertiser_required

log = logging.getLogger(__name__)


@advertiser_required
def banners(request):
    orders = list(BannerOrder.objects.filter(user=request.user).select_related("slot"))
    live = [b for b in orders if b.is_live]
    return _page(request, "advertise/banners.html", {"orders": orders, "slots": BannerSlot.objects.filter(active=True),
        "n_live": len(live), "n_views": sum(b.views for b in live), "n_clicks": sum(b.clicks for b in live)}, "banners")


@advertiser_required
def new_banner(request):
    slots = list(BannerSlot.objects.filter(active=True))
    if not slots:
        messages.info(request, _("Banner places are being prepared. Please check back soon."))
        return redirect("ad_banners")
    chosen = next((s for s in slots if s.place == request.GET.get("place") and s.free), None) or next((s for s in slots if s.free), slots[0])
    adv = getattr(request.user, "advertiser", None)
    form = BannerOrderForm(request.POST or None, request.FILES or None, initial={"slot": chosen, "business_name": adv.name if adv else ""})
    if request.method == "POST":
        if form.is_valid():
            b = form.save(commit=False); b.user = request.user; b.save()
            messages.success(request, _("Your banner is ready. One last step: pay to book the place."))
            return redirect("ad_banner", token=b.token)
        messages.error(request, _("Please check the highlighted fields."))
    return _page(request, "advertise/banner_new.html", {"form": form, "slots": slots, "chosen": chosen}, "banners")


@advertiser_required
def banner_detail(request, token):
    b = get_object_or_404(BannerOrder.objects.select_related("slot"), token=token)
    if b.user_id != request.user.pk and not request.user.is_staff: raise Http404
    p = b.payment
    if p and p.status == "pending" and p.tracking_id and pesapal.configured():   # catch up if Pesapal's notice was missed
        try: pesapal.refresh(p, request); b = BannerOrder.objects.select_related("slot").get(pk=b.pk)
        except pesapal.PesapalError as e: log.warning("Pesapal check failed for %s: %s", p.invoice_no, e)
    can_pay = not b.payment_pending and (b.status in ("awaiting_payment", "rejected") or b.is_live)
    online = pesapal.configured()
    form = None if online else AdPaymentForm(request.POST or None, initial={"phone": getattr(getattr(request.user, "advertiser", None), "phone", "")})
    if request.method == "POST" and can_pay:
        renewal = b.is_live
        desc = f"{'Banner renewal' if renewal else 'Banner'}: {b.business_name} ({b.slot.name}, {b.slot.days} days)"[:160]
        adv = getattr(request.user, "advertiser", None)
        name, phone = (adv.name if adv else b.business_name), (adv.phone if adv else "")
        if online:
            pay = Payment.objects.create(user=request.user, payer_name=name[:100], payer_phone=phone, kind="banner", amount=b.slot.price,
                                         gateway="pesapal", status="pending", description=desc, banner_order=b)
            try:
                pesapal.checkout(pay, request, email=request.user.email, phone=phone, name=name)
            except pesapal.PesapalError as e:
                log.error("Pesapal checkout failed for %s: %s", pay.invoice_no, e)
                pay.status = "failed"; pay.save(update_fields=["status"])
                messages.error(request, _("We could not open the payment page right now. Please try again in a moment."))
                return redirect("ad_banner", token=b.token)
            return redirect(pesapal.pay_page(pay))
        if form.is_valid():   # no Pesapal keys: the payer gives the mobile-money reference and our team confirms it
            d = form.cleaned_data
            pay = Payment.objects.create(user=request.user, payer_name=name[:100], payer_phone=d["phone"], kind="banner", amount=b.slot.price,
                                         gateway=d["gateway"], reference=d["reference"], status="pending", description=desc, banner_order=b)
            for staff in get_user_model().objects.filter(is_staff=True, is_active=True):
                Notification.objects.create(user=staff, link=reverse("dash_manage_edit", args=["banners", b.pk]),
                                            title=f"Banner payment to confirm: {b.business_name}"[:120],
                                            body=f"{b.slot.name} · TSh {pay.amount:,} · {pay.get_gateway_display()} {pay.reference}")
            messages.success(request, _("Asante! We received your payment details. Our team will confirm the payment and check your banner."))
            return redirect("ad_banner", token=b.token)
        messages.error(request, _("Please check the payment details."))
    return _page(request, "advertise/banner_detail.html", {"b": b, "form": form, "can_pay": can_pay, "online": online,
        "history": b.payments.order_by("-created", "-pk")}, "banners")


def click(request, token):
    """A tap on a banner: count it, then go to the advertiser's link."""
    b = BannerOrder.objects.live().filter(token=token).first()
    if b is None: return redirect("home")
    BannerOrder.objects.filter(pk=b.pk).update(clicks=F("clicks") + 1)
    return HttpResponseRedirect(b.target)
