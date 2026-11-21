"""Advertise with us: the landing page, the advert request form and the vendor's order page (pay, track, renew)."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Avg, Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from .forms import LOCATIONS
from .forms_ads import AdOrderForm, AdPaymentForm
from .models import AdOrder, AdPackage, Advert, Member, Notification, Payment, ServiceCategory, Vendor


def advertise(request):
    stats = cache.get("advertise-stats")
    if stats is None:   # real numbers, refreshed every 10 minutes
        stats = {"members": Member.objects.count(), "views": Advert.objects.aggregate(v=Sum("views"))["v"] or 0,
                 "vendors": Vendor.objects.count(), "categories": ServiceCategory.objects.count(), "regions": len(LOCATIONS)}
        cache.set("advertise-stats", stats, 600)
    examples = (Advert.objects.live().select_related("vendor", "category")
                .annotate(rating=Avg("reviews__rating"), n_reviews=Count("reviews")).order_by("-featured", "-views")[:3])
    mine = AdOrder.objects.filter(user=request.user).select_related("package", "advert")[:5] if request.user.is_authenticated else []
    return render(request, "advertise/landing.html", {"packages": AdPackage.objects.filter(active=True), "stats": stats,
        "categories": ServiceCategory.objects.order_by("order", "pk"), "examples": examples, "mine": mine, "wished": set()})


def advertise_start(request):
    packages = AdPackage.objects.filter(active=True)
    if not packages.exists():
        messages.info(request, _("Advert packages are being prepared. Please check back soon."))
        return redirect("advertise")
    chosen = packages.filter(slug=request.GET.get("package")).first() or packages.filter(popular=True).first() or packages.first()
    member = getattr(request.user, "member", None) if request.user.is_authenticated else None
    initial = {"package": chosen, "contact_name": member.name if member else "", "phone": member.phone if member else "",
               "email": request.user.email if request.user.is_authenticated else "", "city": member.city if member else "",
               "category": request.GET.get("category") or None}
    form = AdOrderForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST":
        if form.is_valid():
            order = form.save(commit=False)
            order.user = request.user if request.user.is_authenticated else None
            order.save()
            messages.success(request, _("Your advert is ready. One last step: pay to publish it."))
            return redirect(order)
        messages.error(request, _("Please check the highlighted fields."))
    return render(request, "advertise/start.html", {"form": form, "packages": packages, "chosen": chosen,
                                                    "categories": ServiceCategory.objects.order_by("order", "pk")})


def ad_order(request, token):
    order = get_object_or_404(AdOrder.objects.select_related("package", "category", "advert"), token=token)
    can_pay = not order.payment_pending and order.status in ("awaiting_payment", "rejected", "live")
    form = AdPaymentForm(request.POST or None, initial={"phone": order.phone})
    if request.method == "POST" and can_pay:
        if form.is_valid():
            d, renewal = form.cleaned_data, order.status == "live"
            p = Payment.objects.create(user=order.user, payer_name=order.business_name[:100], payer_phone=d["phone"], kind="advert",
                                       amount=order.package.price, gateway=d["gateway"], reference=d["reference"], status="pending",
                                       description=f"{'Renewal' if renewal else 'Advert'}: {order.title} ({order.package.name}, {order.package.days} days)"[:160],
                                       ad_order=order)
            if not renewal: order.status = "paid"; order.save(update_fields=["status"])
            for staff in get_user_model().objects.filter(is_staff=True, is_active=True):
                Notification.objects.create(user=staff, link=reverse("dash_manage_edit", args=["ad-orders", order.pk]),
                                            title=f"Advert payment to confirm: {order.business_name}"[:120],
                                            body=f"{order.package.name} · TSh {p.amount:,} · {p.get_gateway_display()} {p.reference}")
            messages.success(request, _("Asante! We received your payment details. Your advert goes live as soon as our team confirms the payment."))
            return redirect(order)
        messages.error(request, _("Please check the payment details."))
    ad = order.advert
    return render(request, "advertise/order.html", {"o": order, "form": form, "can_pay": can_pay, "ad": ad,
        "inquiries": ad.inquiries.count() if ad else 0, "history": order.payments.order_by("-created", "-pk"),
        "page_url": request.build_absolute_uri(order.get_absolute_url())})
