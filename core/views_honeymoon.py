"""Honeymoon destinations, packages and booking requests."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from .forms import BookingForm, PackageReviewForm
from .models import Destination, HoneymoonSave, Notification, Package
from .views import safe_next

DURATIONS = [("1-3", "1 - 3 Days", Q(days__lte=3)), ("4-7", "4 - 7 Days", Q(days__gte=4, days__lte=7)),
             ("8-10", "8 - 10 Days", Q(days__gte=8, days__lte=10)), ("10+", "More than 10 Days", Q(days__gt=10))]
RATINGS = [("4.5", 4.5, 4.5), ("4.0", 4.0, 4.0), ("3.0", 3.0, 3.0)]   # key, minimum, stars to draw
STRIP = [("beach", "Beach & Islands"), ("safari", "Safari & Nature"), ("mountains", "Mountains"), ("city", "Luxury Cities"), ("resort", "Luxury Resorts"),
         ("romantic", "Romantic Getaways"), ("tanzania", "Tanzania"), ("east-africa", "East Africa"), ("international", "International")]
OFFERS = [("discount", "Honeymoon Discount", "discount"), ("free", "Free Add-ons", "free_addons"), ("all", "All Inclusive", "all_inclusive")]
SORTS = [("popular", "Most Popular"), ("price", "Price: Low to High"), ("-price", "Price: High to Low"), ("rating", "Top Rated"), ("short", "Shortest Trip")]

def saved(request):
    if not request.user.is_authenticated: return set(), set()
    rows = HoneymoonSave.objects.filter(user=request.user).values_list("destination_id", "package_id")
    return {d for d, _ in rows if d}, {p for _, p in rows if p}

def money(v):
    try: return int(str(v).replace(",", "").strip())
    except ValueError: return None

HERO_FEATS = [("palm", "Stunning Locations"), ("gem", "Luxury Resorts"), ("people", "Curated for Couples"), ("shield-c", "Safe & Trusted"), ("heart-f", "Unforgettable Experiences")]
PKG_FEATS = [("heart", "Romantic Experiences"), ("bed", "Luxury Accommodation"), ("plane", "Seamless Travel"), ("gem", "Special Couple Offers")]

def page_links(request, pg):
    params = request.GET.copy(); params.pop("page", None)
    base = params.copy(); base.pop("view", None)
    return {"pg": pg, "qs": params.urlencode(), "qs_base": base.urlencode(), "pages": pg.paginator.get_elided_page_range(pg.number, on_each_side=2, on_ends=1)}

def sort_by(qs, key, price_field):
    order = {"price": [price_field], "-price": [f"-{price_field}"], "rating": ["-rating", "-reviews"], "short": ["days", price_field]}
    return qs.order_by(*order.get(key, ["-featured", "-reviews", "order"]))

def checked(g, key):
    return [v for v in g.getlist(key) if v]

# ---------- destinations ----------
def destinations(request):
    g = request.GET
    base = Destination.objects.filter(active=True)
    # every count in the sidebar and the picture strip in one query
    agg = {f"k_{k}": Count("pk", filter=Q(kind=k)) for k, _ in Destination.KINDS}
    agg.update({f"r_{k}": Count("pk", filter=Q(region=k)) for k, _ in Destination.REGIONS})
    agg.update({f"d_{k}": Count("pk", filter=q) for k, _, q in DURATIONS})
    agg.update({f"s_{k.replace('.', '')}": Count("pk", filter=Q(rating__gte=v)) for k, v, _ in RATINGS})
    agg["all"] = Count("pk")
    n = base.aggregate(**agg)
    qs = base
    cat = g.get("cat", "")
    if cat in dict(Destination.KINDS): qs = qs.filter(kind=cat)
    elif cat in dict(Destination.REGIONS): qs = qs.filter(region=cat)
    kinds = [k for k in checked(g, "type") if k in dict(Destination.KINDS)]
    if kinds: qs = qs.filter(kind__in=kinds)
    regions = [k for k in checked(g, "region") if k in dict(Destination.REGIONS)]
    if regions: qs = qs.filter(region__in=regions)
    if g.get("country"): qs = qs.filter(country=g["country"])
    lo, hi = money(g.get("min", "")), money(g.get("max", ""))
    if lo: qs = qs.filter(from_price__gte=lo)
    if hi: qs = qs.filter(from_price__lte=hi)
    durs = [k for k in checked(g, "dur") if k in {d[0] for d in DURATIONS}]
    if durs:
        q = Q()
        for k, _, cond in DURATIONS:
            if k in durs: q |= cond
        qs = qs.filter(q)
    rating = next((v for k, v, _ in RATINGS if g.get("rating") == k), None)
    if rating: qs = qs.filter(rating__gte=rating)
    if g.get("q"): qs = qs.filter(Q(name__icontains=g["q"]) | Q(country__icontains=g["q"]) | Q(tagline__icontains=g["q"]))
    sort = g.get("sort") if g.get("sort") in dict(SORTS) else "popular"
    qs = sort_by(qs.annotate(n_packages=Count("packages", filter=Q(packages__active=True))), sort, "from_price")
    pg = Paginator(qs, 10).get_page(g.get("page"))
    saved_d, _ = saved(request)
    pg.object_list = list(pg.object_list)
    for d in pg.object_list: d.is_saved = d.pk in saved_d
    filtered = any(g.get(k) for k in ("cat", "type", "region", "country", "min", "max", "dur", "rating", "q"))
    return render(request, "honeymoon/destinations.html", {
        **page_links(request, pg), "hero_feats": HERO_FEATS, "f": g, "cat": cat, "sort": sort, "sorts": SORTS, "view": g.get("view", "grid"), "filtered": filtered,
        "strip": [(k, label, n.get(f"k_{k}", n.get(f"r_{k}", 0))) for k, label in STRIP], "n": n,
        "kinds": [(k, label, n[f"k_{k}"]) for k, label in Destination.KINDS] + [(k, label, n[f"r_{k}"]) for k, label in Destination.REGIONS],
        "sel_types": kinds + regions, "durations": [(k, label, n[f"d_{k}"]) for k, label, _ in DURATIONS], "sel_durs": durs,
        "ratings": [(k, label, n[f"s_{k.replace('.', '')}"]) for k, label, _ in RATINGS],
        "countries": base.values_list("country", flat=True).distinct().order_by("country"), "saved": saved_d})

# ---------- packages ----------
def packages(request, slug=None):
    g = request.GET
    dest = get_object_or_404(Destination, slug=slug, active=True) if slug else None
    base = Package.objects.filter(active=True, destination__active=True)
    if dest: base = base.filter(destination=dest)
    agg = {f"t_{k}": Count("pk", filter=Q(package_type=k)) for k, _ in Package.TYPES}
    agg.update({f"d_{k}": Count("pk", filter=q) for k, _, q in DURATIONS})
    agg.update({f"s_{k}": Count("pk", filter=Q(stars=k)) for k in (5, 4, 3)})
    agg.update({f"o_{k}": Count("pk", filter=Q(**{field: True})) for k, _, field in OFFERS})
    agg["all"] = Count("pk")
    n = base.aggregate(**agg)
    qs = base.select_related("destination")
    types = [k for k in checked(g, "type") if k in dict(Package.TYPES)]
    if types: qs = qs.filter(package_type__in=types)
    durs = [k for k in checked(g, "dur") if k in {d[0] for d in DURATIONS}]
    if durs:
        q = Q()
        for k, _, cond in DURATIONS:
            if k in durs: q |= cond
        qs = qs.filter(q)
    lo, hi = money(g.get("min", "")), money(g.get("max", ""))
    if lo: qs = qs.filter(price__gte=lo)
    if hi: qs = qs.filter(price__lte=hi)
    stars = [int(s) for s in checked(g, "stars") if s in ("3", "4", "5")]
    if stars: qs = qs.filter(stars__in=stars)
    offers = [k for k in checked(g, "offer") if k in {o[0] for o in OFFERS}]
    for k, _, field in OFFERS:
        if k in offers: qs = qs.filter(**{field: True})
    if g.get("q"): qs = qs.filter(Q(title__icontains=g["q"]) | Q(location__icontains=g["q"]))
    sort = g.get("sort") if g.get("sort") in dict(SORTS) else "popular"
    pg = Paginator(sort_by(qs, sort, "price"), 8).get_page(g.get("page"))
    _, saved_p = saved(request)
    pg.object_list = list(pg.object_list)
    for p in pg.object_list: p.is_saved = p.pk in saved_p
    crumbs = [("Home", reverse("home")), ("Honeymoon Destinations", reverse("hm_destinations"))]
    crumbs += [(dest.name, dest.get_absolute_url()), ("View Packages", None)] if dest else [("All Packages", None)]
    dests = Destination.objects.filter(active=True).annotate(n=Count("packages", filter=Q(packages__active=True))).filter(n__gt=0)
    return render(request, "honeymoon/packages.html", {
        **page_links(request, pg), "hero_feats": PKG_FEATS, "crumbs": crumbs, "f": g, "dest": dest, "dests": dests, "n": n, "sort": sort, "sorts": SORTS, "view": g.get("view", "grid"),
        "types": [(k, label, n[f"t_{k}"]) for k, label in Package.TYPES], "sel_types": types,
        "durations": [(k, label, n[f"d_{k}"]) for k, label, _ in DURATIONS], "sel_durs": durs,
        "star_opts": [(k, n[f"s_{k}"]) for k in (5, 4, 3)], "sel_stars": stars,
        "offers": [(k, label, n[f"o_{k}"]) for k, label, _ in OFFERS], "sel_offers": offers, "saved": saved_p,
        "filtered": any(g.get(k) for k in ("type", "dur", "min", "max", "stars", "offer", "q"))})

def package(request, slug):
    p = get_object_or_404(Package.objects.select_related("destination"), slug=slug, active=True, destination__active=True)
    photos = list(p.photos.all())
    gallery = ([p.image.url] if p.image else []) + [ph.image.url for ph in photos]
    others = Package.objects.filter(active=True, destination__active=True).exclude(pk=p.pk).select_related("destination").order_by("-featured", "order")
    similar = list(others.filter(destination=p.destination)[:5])   # same destination first, then the best of the rest
    if len(similar) < 5: similar += list(others.exclude(destination=p.destination)[:5 - len(similar)])
    member = getattr(request.user, "member", None) if request.user.is_authenticated else None
    initial = {"couples": 1}
    if request.user.is_authenticated:
        initial.update(name=member.name if member else request.user.get_full_name(), phone=member.phone if member else "", email=request.user.email)
    reviews = list(p.member_reviews.select_related("user__member")[:20])
    mine = request.user.is_authenticated and p.member_reviews.filter(user=request.user).exists()
    _, saved_p = saved(request)
    p.is_saved = p.pk in saved_p
    for x in similar: x.is_saved = x.pk in saved_p
    crumbs = [("Home", reverse("home")), ("Honeymoon Destinations", reverse("hm_destinations")),
              (p.destination.name, p.destination.get_absolute_url()), (p.title, None)]
    return render(request, "honeymoon/package.html", {
        "p": p, "crumbs": crumbs, "gallery": gallery, "photos": photos, "similar": similar, "form": BookingForm(initial=initial), "reviews": reviews,
        "review_form": None if mine else PackageReviewForm(), "saved": saved_p})

@require_POST
def book(request, slug):
    p = get_object_or_404(Package, slug=slug, active=True)
    form = BookingForm(request.POST)
    if form.is_valid():
        b = form.save(commit=False)
        b.package, b.user = p, request.user if request.user.is_authenticated else None
        b.save()
        if b.user:
            Notification.objects.create(user=b.user, title=f"Booking request received: {p.title}", link=p.get_absolute_url(),
                                        body=f"Asante! Our travel team will call you on {b.phone} to confirm dates and payment.")
        messages.success(request, f"Asante! Your request for {p.title} was sent. Our travel team will contact you on {b.phone} very soon.")
        return redirect(p.get_absolute_url())
    errors = "; ".join(f"{form.fields[k].label if k in form.fields else ''}: {' '.join(v)}".strip(": ") for k, v in form.errors.items())
    messages.error(request, f"Please check the booking form. {errors}")
    return redirect(p.get_absolute_url() + "#book")

@login_required
@require_POST
def review(request, slug):
    p = get_object_or_404(Package, slug=slug, active=True)
    form = PackageReviewForm(request.POST)
    if form.is_valid() and not p.member_reviews.filter(user=request.user).exists():
        form.instance.package, form.instance.user = p, request.user
        form.save(); messages.success(request, "Thank you for your review.")
    return redirect(p.get_absolute_url() + "#reviews")

@login_required
@require_POST
def save(request):
    kind, pk = request.POST.get("kind"), request.POST.get("pk", "")
    if kind not in ("destination", "package") or not pk.isdigit(): return redirect("hm_destinations")
    obj = get_object_or_404(Destination if kind == "destination" else Package, pk=pk)
    row, created = HoneymoonSave.objects.get_or_create(user=request.user, **{kind: obj})
    if not created: row.delete()
    messages.success(request, f"{obj} {'saved to' if created else 'removed from'} your favourites.")
    return redirect(safe_next(request) or obj.get_absolute_url())
