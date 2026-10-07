from datetime import date
from django.contrib import messages
from django.contrib.auth import login, views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .forms import LOCATIONS, LoginForm, SignupForm, ProfileForm, MessageForm, ReportForm
from .models import *

AGES = {"20-35": (20, 35), "25-40": (25, 40), "35+": (35, 99)}

def liked_ids(request):
    return set(request.user.likes.values_list("member_id", flat=True)) if request.user.is_authenticated else set()

def safe_next(request):
    nxt = request.POST.get("next") or request.GET.get("next")
    return nxt if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}, request.is_secure()) else None

def me(request):
    return getattr(request.user, "member", None) if request.user.is_authenticated else None

def faces():
    return Member.objects.exclude(photo="").filter(verified=True).order_by("joined", "pk")[:5]

def home(request):
    gold = Plan.objects.filter(price__gt=0).order_by("price").first()
    return render(request, "home.html", {
        "categories": ServiceCategory.objects.all()[:8],
        "matches": Member.objects.filter(featured=True).order_by("joined", "pk")[:4],
        "faces": faces(),
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
    qs = qs.annotate(extra_photos=Count("photos")).order_by(*Member._meta.ordering, "pk")
    page = Paginator(qs, 12).get_page(q.get("page"))
    params = q.copy(); params.pop("page", None)
    return render(request, "matches.html", {"page": page, "locations": LOCATIONS, "ages": AGES, "f": q, "seek": seek, "religions": Member.RELIGION,
                                            "qs": params.urlencode(), "liked": liked_ids(request)})

@login_required
def member_detail(request, pk):
    m, mine = get_object_or_404(Member, pk=pk), me(request)
    # previous / next follow the Find a Match order for the same gender
    ids = list(Member.objects.filter(gender=m.gender).exclude(pk=getattr(mine, "pk", None)).values_list("pk", flat=True))
    i = ids.index(m.pk) if m.pk in ids else -1
    return render(request, "member.html", {"m": m, "liked": liked_ids(request), "is_me": m == mine, "gallery": m.photos.all(),
        "prev_id": ids[i - 1] if i > 0 else None, "next_id": ids[i + 1] if 0 <= i < len(ids) - 1 else None,
        "shortlisted": Shortlist.objects.filter(user=request.user, member=m).exists(), "report_form": ReportForm()})

@login_required
@require_POST
def shortlist(request, pk):
    m = get_object_or_404(Member, pk=pk)
    obj, created = Shortlist.objects.get_or_create(user=request.user, member=m)
    if not created: obj.delete()
    messages.success(request, f"{m.name} {'added to' if created else 'removed from'} your shortlist.")
    return redirect(safe_next(request) or reverse("member", args=[pk]))

@login_required
@require_POST
def report(request, pk):
    m = get_object_or_404(Member, pk=pk)
    form = ReportForm(request.POST)
    if form.is_valid():
        form.instance.member, form.instance.reporter = m, request.user; form.save()
        messages.success(request, "Thank you. Our team will review this profile.")
    return redirect(reverse("member", args=[pk]))

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
    return redirect(safe_next(request) or reverse("member", args=[pk]))

@login_required
def my_likes(request):
    members = Member.objects.filter(likes__user=request.user).order_by("-likes__created")
    shortlisted = Member.objects.filter(shortlisted_by__user=request.user).order_by("-shortlisted_by__created")
    return render(request, "likes.html", {"members": members, "shortlisted": shortlisted, "liked": liked_ids(request)})

class LoginView(auth_views.LoginView):
    """Django's LoginView puts the current Site object in the context as "site"; restore our SiteSetting."""
    redirect_authenticated_user = True
    authentication_form = LoginForm
    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "site": SiteSetting.load(), "faces": faces()}
    def form_valid(self, form):
        response = super().form_valid(form)
        if not self.request.POST.get("remember"): self.request.session.set_expiry(0)  # end session when the browser closes
        return response

def signup(request):
    if request.user.is_authenticated: return redirect("home")
    form = SignupForm(request.POST or None)
    if form.is_valid():
        user = form.save(); login(request, user)
        messages.success(request, "Karibu Sakinah! Complete your profile so others can get to know you.")
        return redirect(safe_next(request) or "profile_edit")
    return render(request, "registration/signup.html", {"form": form, "next": safe_next(request) or "", "faces": faces()})

@login_required
def profile_edit(request):
    m = me(request) or Member(user=request.user, name=request.user.get_full_name() or request.user.username, age=18)
    form = ProfileForm(request.POST or None, request.FILES or None, instance=m)
    if form.is_valid():
        form.save(); messages.success(request, "Profile saved.")
        return redirect("member", pk=form.instance.pk)
    return render(request, "profile_edit.html", {"form": form})

def thread_qs(user, mine, other):
    q = Q(sender=user, to=other)
    if other.user_id and mine: q |= Q(sender=other.user, to=mine)
    return Message.objects.filter(q).select_related("sender")

@login_required
def thread(request, pk):
    other, mine = get_object_or_404(Member, pk=pk), me(request)
    if other == mine: return redirect("inbox")
    form = MessageForm(request.POST or None)
    if form.is_valid():
        Message.objects.create(sender=request.user, to=other, body=form.cleaned_data["body"])
        return redirect("thread", pk=pk)
    if mine and other.user_id: Message.objects.filter(sender=other.user, to=mine, read=False).update(read=True)
    return render(request, "thread.html", {"other": other, "msgs": thread_qs(request.user, mine, other), "form": form})

@login_required
def inbox(request):
    mine, convos = me(request), {}
    q = Q(sender=request.user) | (Q(to=mine) if mine else Q(pk__in=[]))
    for msg in Message.objects.filter(q).select_related("to", "sender__member").order_by("-created"):
        other = msg.to if msg.sender_id == request.user.id else getattr(msg.sender, "member", None)
        if other is None or other == mine: continue
        c = convos.setdefault(other.pk, {"member": other, "last": msg, "unread": 0})
        if msg.to == mine and not msg.read: c["unread"] += 1
    return render(request, "inbox.html", {"convos": convos.values()})


@login_required
def notifications(request):
    notes = list(request.user.notifications.all()[:50])
    request.user.notifications.filter(read=False).update(read=True)
    return render(request, "notifications.html", {"notes": notes})
