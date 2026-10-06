from datetime import date
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .forms import LOCATIONS, SignupForm, ProfileForm
from .models import *

AGES = {"20-35": (20, 35), "25-40": (25, 40), "35+": (35, 99)}

def liked_ids(request):
    return set(request.user.likes.values_list("member_id", flat=True)) if request.user.is_authenticated else set()

def me(request):
    return getattr(request.user, "member", None) if request.user.is_authenticated else None

def home(request):
    gold = Plan.objects.order_by("price").first()
    return render(request, "home.html", {
        "categories": ServiceCategory.objects.all()[:8],
        "matches": Member.objects.filter(featured=True).order_by("joined", "pk")[:4],
        "events": Event.objects.filter(date__gte=date.today())[:3],
        "perks": PremiumPerk.objects.all(),
        "from_price": gold.price if gold else 0,
        "strip": FeatureStrip.objects.all(),
        "locations": LOCATIONS,
        "liked": liked_ids(request),
    })

def matches(request):
    q, mine = request.GET, me(request)
    seek = q.get("seek") or ({"F": "M", "M": "F"}.get(mine.gender) if mine else "")
    qs = Member.objects.all()
    if mine: qs = qs.exclude(pk=mine.pk)
    if seek in ("F", "M"): qs = qs.filter(gender=seek)
    if q.get("age") in AGES:
        lo, hi = AGES[q["age"]]; qs = qs.filter(age__gte=lo, age__lte=hi)
    if q.get("city"): qs = qs.filter(city=q["city"])
    if q.get("religion"): qs = qs.filter(religion=q["religion"])
    if q.get("verified"): qs = qs.filter(verified=True)
    page = Paginator(qs, 12).get_page(q.get("page"))
    params = q.copy(); params.pop("page", None)
    return render(request, "matches.html", {"page": page, "locations": LOCATIONS, "ages": AGES, "f": q, "seek": seek,
                                            "qs": params.urlencode(), "liked": liked_ids(request)})

def member_detail(request, pk):
    m = get_object_or_404(Member, pk=pk)
    return render(request, "member.html", {"m": m, "liked": liked_ids(request), "is_me": m == me(request)})

@login_required
@require_POST
def like(request, pk):
    m = get_object_or_404(Member, pk=pk)
    if m == me(request):
        messages.error(request, "You cannot like your own profile.")
    else:
        obj, created = Like.objects.get_or_create(user=request.user, member=m)
        if not created: obj.delete()
        messages.success(request, f"You liked {m.name}." if created else f"Like removed for {m.name}.")
    nxt = request.POST.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}, request.is_secure()): return redirect(nxt)
    return redirect("member", pk=pk)

@login_required
def my_likes(request):
    members = Member.objects.filter(likes__user=request.user).order_by("-likes__created")
    return render(request, "likes.html", {"members": members, "liked": liked_ids(request)})

def signup(request):
    if request.user.is_authenticated: return redirect("home")
    form = SignupForm(request.POST or None)
    if form.is_valid():
        user = form.save(); login(request, user)
        messages.success(request, "Welcome! Complete your profile so others can get to know you.")
        return redirect("profile_edit")
    return render(request, "registration/signup.html", {"form": form})

@login_required
def profile_edit(request):
    m = me(request) or Member(user=request.user, name=request.user.get_full_name() or request.user.username, age=18)
    form = ProfileForm(request.POST or None, request.FILES or None, instance=m)
    if form.is_valid():
        form.save(); messages.success(request, "Profile saved.")
        return redirect("member", pk=form.instance.pk)
    return render(request, "profile_edit.html", {"form": form})

def events(request):
    return render(request, "events.html", {"upcoming": Event.objects.filter(date__gte=date.today()),
                                           "past": Event.objects.filter(date__lt=date.today()).order_by("-date")[:6]})

def services(request):
    return render(request, "services.html", {"categories": ServiceCategory.objects.all()})

def premium(request):
    return render(request, "premium.html", {"plans": Plan.objects.all(), "perks": PremiumPerk.objects.all()})
