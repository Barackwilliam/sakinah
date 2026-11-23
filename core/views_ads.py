"""Advertise with us. The landing page is public. Advertisers have their own accounts, separate from members' (people
looking for a spouse): their own sign-up and login, and their own dashboard (/advertise/dashboard/) where they create
adverts, pay for them and follow their results."""
import logging
from django.contrib import messages
from django.contrib.auth import get_user_model
from functools import wraps
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.core.cache import cache
from django.db.models import Avg, Count, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from . import pesapal
from .forms import LOCATIONS
from .forms_ads import AdOrderForm, AdPaymentForm, AdvertiserAccountForm, AdvertiserLoginForm, AdvertiserSignupForm
from .models import AdOrder, AdPackage, Advert, Advertiser, Member, Notification, Payment, ServiceCategory, SiteSetting, Vendor
from .views import safe_next

log = logging.getLogger(__name__)


def advertise(request):
    stats = cache.get("advertise-stats")
    if stats is None:   # real numbers, refreshed every 10 minutes
        stats = {"members": Member.objects.count(), "views": Advert.objects.aggregate(v=Sum("views"))["v"] or 0,
                 "vendors": Vendor.objects.count(), "categories": ServiceCategory.objects.count(), "regions": len(LOCATIONS)}
        cache.set("advertise-stats", stats, 600)
    examples = (Advert.objects.live().select_related("vendor", "category")
                .annotate(rating=Avg("reviews__rating"), n_reviews=Count("reviews")).order_by("-featured", "-views")[:3])
    mine = (AdOrder.objects.filter(user=request.user).select_related("package", "advert")[:5]
            if request.user.is_authenticated and hasattr(request.user, "advertiser") else [])
    from .models import BannerSlot
    return render(request, "advertise/landing.html", {"packages": AdPackage.objects.filter(active=True), "stats": stats,
        "slots": BannerSlot.objects.filter(active=True),
        "categories": ServiceCategory.objects.order_by("order", "pk"), "examples": examples, "mine": mine, "wished": set()})


# old links (public pages and the member area) keep working: they now open in the advertiser dashboard
def advertise_start(request):
    return redirect(reverse("ad_new") + (f"?{request.GET.urlencode()}" if request.GET else ""))

def ad_order(request, token):
    return redirect("ad_detail", token=token)

def old_list(request): return redirect("ad_dashboard")
def old_new(request): return advertise_start(request)
def old_detail(request, token): return redirect("ad_detail", token=token)


def advertiser_required(view):
    """The advertiser dashboard: signed-in advertisers only. Visitors are asked to sign up or log in as an advertiser."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('ad_register')}?next={request.get_full_path()}")
        if not hasattr(request.user, "advertiser") and not request.user.is_staff:
            return redirect(f"{reverse('ad_register')}?next={request.get_full_path()}")
        return view(request, *args, **kwargs)
    return wrapper


def _page(request, template, ctx, nav="adverts"):
    adv = getattr(request.user, "advertiser", None)
    notes = Notification.objects.filter(user=request.user)
    return render(request, template, {"site": SiteSetting.load(), "adv": adv, "nav": nav, "no_search": True,
                                      "n_notes": notes.filter(read=False).count(), **ctx})


def _home(user): return reverse("dashboard") if user.is_staff else reverse("ad_dashboard")


def register(request):
    """Create an advertiser account: full name, phone, email, password and the advertising policy."""
    if request.user.is_authenticated and (hasattr(request.user, "advertiser") or request.user.is_staff):
        return redirect(safe_next(request) or _home(request.user))
    form = AdvertiserSignupForm(request.POST or None) if not request.user.is_authenticated else None
    if form is not None and form.is_valid():
        user = form.save()
        login(request, user, backend="core.backends.EmailOrUsernameBackend")
        from .verify import start
        nxt = safe_next(request) or reverse("ad_dashboard")
        if start(request, user):   # a code and a link are on their way
            return redirect(reverse("verify_email") + f"?next={nxt}")
        messages.success(request, _("Karibu! Your advertiser account is ready. Create your first advert."))
        return redirect(nxt)
    return render(request, "advertise/register.html", {"form": form, "next": safe_next(request) or "", "site": SiteSetting.load(),
                                                       "packages": AdPackage.objects.filter(active=True)})


class LoginView(auth_views.LoginView):
    """The advertisers' own login. Members log in on /login/."""
    template_name = "advertise/login.html"
    authentication_form = AdvertiserLoginForm
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and (hasattr(request.user, "advertiser") or request.user.is_staff):
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "site": SiteSetting.load()}
    def form_valid(self, form):
        response = super().form_valid(form)
        if not self.request.POST.get("remember"): self.request.session.set_expiry(0)
        return response
    def get_default_redirect_url(self): return _home(self.request.user)


@advertiser_required
def account(request):
    """The advertiser's details and password."""
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.forms import PasswordChangeForm
    adv = getattr(request.user, "advertiser", None)
    if adv is None: return redirect("dashboard")
    form = AdvertiserAccountForm(request.POST if request.POST.get("action") == "details" else None, instance=adv)
    pw = PasswordChangeForm(request.user, request.POST if request.POST.get("action") == "password" else None)
    if request.method == "POST":
        if request.POST.get("action") == "details" and form.is_valid():
            form.save(); messages.success(request, _("Your details are saved."))
            return redirect("ad_account")
        if request.POST.get("action") == "password" and pw.is_valid():
            pw.save(); update_session_auth_hash(request, pw.user)
            messages.success(request, _("Your password is changed."))
            return redirect("ad_account")
        messages.error(request, _("Please check the highlighted fields."))
    return _page(request, "advertise/dash_account.html", {"form": form, "pw": pw}, "account")


@advertiser_required
def notifications(request):
    notes = list(Notification.objects.filter(user=request.user)[:50])
    Notification.objects.filter(user=request.user, read=False).update(read=True)
    return _page(request, "advertise/dash_notifications.html", {"notes": notes}, "notifications")


@advertiser_required
def my_adverts(request):
    orders = list(AdOrder.objects.filter(user=request.user).select_related("package", "advert", "category"))
    live = [o for o in orders if o.status == "live" and not o.is_expired]
    return _page(request, "advertise/dash_list.html", {"orders": orders, "n_live": len(live),
        "n_views": sum(o.advert.views for o in live if o.advert), "packages": AdPackage.objects.filter(active=True)})


@advertiser_required
def new_advert(request):
    packages = AdPackage.objects.filter(active=True)
    if not packages.exists():
        messages.info(request, _("Advert packages are being prepared. Please check back soon."))
        return redirect("ad_dashboard")
    chosen = packages.filter(slug=request.GET.get("package")).first() or packages.filter(popular=True).first() or packages.first()
    adv = getattr(request.user, "advertiser", None)
    initial = {"package": chosen, "contact_name": adv.name if adv else "", "phone": adv.phone if adv else "",
               "email": request.user.email, "category": request.GET.get("category") or None}
    form = AdOrderForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST":
        if form.is_valid():
            order = form.save(commit=False)
            order.user = request.user
            order.save()
            messages.success(request, _("Your advert is ready. One last step: pay to publish it."))
            return redirect("ad_detail", token=order.token)
        messages.error(request, _("Please check the highlighted fields."))
    return _page(request, "advertise/dash_new.html", {"form": form, "packages": packages, "chosen": chosen}, "new")


@advertiser_required
def advert_detail(request, token):
    order = get_object_or_404(AdOrder.objects.select_related("package", "category", "advert"), token=token)
    if order.user_id != request.user.pk and not request.user.is_staff: raise Http404
    p = order.payment
    if p and p.status == "pending" and p.tracking_id and pesapal.configured():   # catch up if Pesapal's notice was missed
        try: pesapal.refresh(p, request); order = AdOrder.objects.select_related("package", "category", "advert").get(pk=order.pk)
        except pesapal.PesapalError as e: log.warning("Pesapal check failed for %s: %s", p.invoice_no, e)
    can_pay = not order.payment_pending and order.status in ("awaiting_payment", "rejected", "live")
    online = pesapal.configured()
    form = None if online else AdPaymentForm(request.POST or None, initial={"phone": order.phone})
    if request.method == "POST" and can_pay:
        renewal = order.status == "live"
        desc = f"{'Renewal' if renewal else 'Advert'}: {order.title} ({order.package.name}, {order.package.days} days)"[:160]
        if online:
            pay = Payment.objects.create(user=request.user, payer_name=order.business_name[:100], payer_phone=order.phone, kind="advert",
                                         amount=order.package.price, gateway="pesapal", status="pending", description=desc, ad_order=order)
            try:
                url = pesapal.checkout(pay, request, email=order.email or request.user.email, phone=order.phone, name=order.contact_name)
            except pesapal.PesapalError as e:
                log.error("Pesapal checkout failed for %s: %s", pay.invoice_no, e)
                pay.status = "failed"; pay.save(update_fields=["status"])
                messages.error(request, _("We could not open the payment page right now. Please try again in a moment."))
                return redirect("ad_detail", token=order.token)
            return redirect(url)
        if form.is_valid():   # no Pesapal keys yet: the payer enters the mobile-money reference and staff confirm
            d = form.cleaned_data
            pay = Payment.objects.create(user=request.user, payer_name=order.business_name[:100], payer_phone=d["phone"], kind="advert",
                                         amount=order.package.price, gateway=d["gateway"], reference=d["reference"], status="pending",
                                         description=desc, ad_order=order)
            if not renewal: order.status = "paid"; order.save(update_fields=["status"])
            for staff in get_user_model().objects.filter(is_staff=True, is_active=True):
                Notification.objects.create(user=staff, link=reverse("dash_manage_edit", args=["ad-orders", order.pk]),
                                            title=f"Advert payment to confirm: {order.business_name}"[:120],
                                            body=f"{order.package.name} · TSh {pay.amount:,} · {pay.get_gateway_display()} {pay.reference}")
            messages.success(request, _("Asante! We received your payment details. Your advert goes live as soon as our team confirms the payment."))
            return redirect("ad_detail", token=order.token)
        messages.error(request, _("Please check the payment details."))
    ad = order.advert
    return _page(request, "advertise/dash_detail.html", {"o": order, "form": form, "can_pay": can_pay, "online": online, "ad": ad,
        "inquiries": ad.inquiries.count() if ad else 0, "history": order.payments.order_by("-created", "-pk")})
