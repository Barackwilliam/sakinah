from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from .forms import InquiryForm, ReviewForm
from .models import Advert, AdvertReview, ServiceCategory, Vendor, Wishlist
from .views import safe_next

def services(request):
    q, cat, vendor = request.GET.get("q", ""), request.GET.get("cat", ""), request.GET.get("vendor", "")
    ads = Advert.objects.filter(active=True).select_related("vendor", "category").annotate(rating=Avg("reviews__rating"), n_reviews=Count("reviews")).order_by("-featured", "-created")
    if cat: ads = ads.filter(category__slug=cat)
    if vendor: ads = ads.filter(vendor__slug=vendor)
    if q: ads = ads.filter(Q(title__icontains=q) | Q(vendor__name__icontains=q) | Q(city__icontains=q))
    return render(request, "services.html", {"categories": ServiceCategory.objects.annotate(n=Count("adverts", filter=Q(adverts__active=True))).order_by("order", "pk"),
        "ads": ads, "cat": cat, "q": q, "vendor": Vendor.objects.filter(slug=vendor).first() if vendor else None,
        "wished": wished_ids(request)})

def wished_ids(request):
    return set(request.user.wishlist.values_list("advert_id", flat=True)) if request.user.is_authenticated else set()

def advert(request, slug):
    ad = get_object_or_404(Advert.objects.select_related("vendor", "category"), slug=slug, active=True)
    Advert.objects.filter(pk=ad.pk).update(views=F("views") + 1)
    stats = ad.reviews.aggregate(avg=Avg("rating"), n=Count("id"))
    vstats = AdvertReview.objects.filter(advert__vendor=ad.vendor).aggregate(avg=Avg("rating"), n=Count("id"))
    member = getattr(request.user, "member", None) if request.user.is_authenticated else None
    my_review = ad.reviews.filter(user=request.user).first() if request.user.is_authenticated else None
    return render(request, "advert.html", {
        "ad": ad, "photos": ad.photos.all(), "stats": stats, "vstats": vstats, "views": ad.views + 1,
        "related": Advert.objects.filter(category=ad.category, active=True).exclude(pk=ad.pk)
                   .annotate(rating=Avg("reviews__rating"), n_reviews=Count("reviews")).order_by("-featured", "-created")[:3],
        "reviews": ad.reviews.select_related("user__member")[:20], "wished": wished_ids(request),
        "inquiry_form": InquiryForm(initial={"name": member.name if member else "", "phone": member.phone if member else ""}),
        "review_form": None if my_review else ReviewForm()})

@login_required
@require_POST
def wishlist(request, slug):
    ad = get_object_or_404(Advert, slug=slug)
    obj, created = Wishlist.objects.get_or_create(user=request.user, advert=ad)
    if not created: obj.delete()
    messages.success(request, f"{ad.title} {'added to' if created else 'removed from'} your wishlist.")
    return redirect(safe_next(request) or reverse("advert", args=[slug]))

@require_POST
def inquire(request, slug):
    ad = get_object_or_404(Advert, slug=slug, active=True)
    form = InquiryForm(request.POST)
    if form.is_valid():
        inquiry = form.save(commit=False)
        inquiry.advert, inquiry.user = ad, request.user if request.user.is_authenticated else None
        inquiry.save()
        messages.success(request, f"Asante! Your request was sent to {ad.vendor.name}. They will contact you soon.")
    else:
        messages.error(request, "Please add your name and phone number so the vendor can reach you.")
    return redirect(reverse("advert", args=[slug]))

@login_required
@require_POST
def review(request, slug):
    ad = get_object_or_404(Advert, slug=slug, active=True)
    form = ReviewForm(request.POST)
    if form.is_valid() and not ad.reviews.filter(user=request.user).exists():
        form.instance.advert, form.instance.user = ad, request.user
        form.save()
        messages.success(request, "Thank you for your review.")
    return redirect(reverse("advert", args=[slug]) + "#reviews")
