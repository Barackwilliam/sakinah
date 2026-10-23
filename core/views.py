from datetime import date, timedelta
from django.contrib import messages
from django.contrib.auth import login, views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .forms import LOCATIONS, LoginForm, SignupForm, ProfileForm, ConversationForm, ReportForm
from .models import *

AGES = {"20-35": (20, 35), "25-40": (25, 40), "35+": (35, 99)}

def liked_ids(request):
    return set(request.user.likes.values_list("member_id", flat=True)) if request.user.is_authenticated else set()

def safe_next(request):
    nxt = request.POST.get("next") or request.GET.get("next")
    # only site paths ("/account/..."): a bare "?tab=x" would be read by redirect() as a view name and crash
    ok = nxt and nxt.startswith("/") and url_has_allowed_host_and_scheme(nxt, {request.get_host()}, request.is_secure())
    return nxt if ok else None

def me(request):
    return getattr(request.user, "member", None) if request.user.is_authenticated else None

def faces():
    return Member.objects.exclude(photo="").filter(verified=True, status="active").order_by("joined", "pk")[:5]

def home(request):
    gold = Plan.objects.filter(price__gt=0).order_by("price").first()
    return render(request, "home.html", {
        "categories": ServiceCategory.objects.all()[:8],
        "destinations": Destination.objects.filter(active=True, featured=True)[:5],
        "matches": Member.objects.filter(featured=True, status="active").order_by("joined", "pk")[:4],
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
    qs = Member.objects.filter(status="active")
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
                                            "qs": params.urlencode(), "liked": liked_ids(request), "call_why": call_block(mine)})

@login_required
def member_detail(request, pk):
    m, mine = get_object_or_404(Member, pk=pk), me(request)
    if mine and m.user_id and Block.objects.filter(user=m.user, member=mine).exists(): raise Http404
    if m.status != "active" and m != mine and not request.user.is_staff: raise Http404
    if request.user.is_authenticated and m != mine and not ProfileView.objects.filter(
            viewer=request.user, member=m, created__gte=timezone.now() - timedelta(minutes=30)).exists():
        ProfileView.objects.create(viewer=request.user, member=m)
    # previous / next follow the Find a Match order for the same gender
    ids = list(Member.objects.filter(gender=m.gender).exclude(pk=getattr(mine, "pk", None)).values_list("pk", flat=True))
    i = ids.index(m.pk) if m.pk in ids else -1
    return render(request, "member.html", {"m": m, "liked": liked_ids(request), "is_me": m == mine, "gallery": m.photos.all(),
        "prev_id": ids[i - 1] if i > 0 else None, "next_id": ids[i + 1] if 0 <= i < len(ids) - 1 else None,
        "shortlisted": Shortlist.objects.filter(user=request.user, member=m).exists(), "report_form": ReportForm(),
        "call_why": call_block_en(mine)})

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

def notify_like(user, liker, m):
    """Tell the liked member (and both people when the like makes a mutual match), respecting their notification settings."""
    if liker is None: return
    mutual = Like.objects.filter(user=m.user, member=liker).exists()
    if mutual:
        for to, other in ((m, liker), (liker, m)):
            if to.user_id and to.notify_matches:
                Notification.objects.create(user=to.user, title=f"It's a match! You and {other.name} like each other", link=reverse("m_messages_with", args=[other.pk]))
    elif m.notify_likes:
        Notification.objects.create(user=m.user, title=f"{liker.name} liked your profile", link=reverse("m_liked"))

@login_required
@require_POST
def like(request, pk):
    m = get_object_or_404(Member, pk=pk)
    if m == me(request):
        messages.error(request, "You cannot like your own profile.")
    else:
        obj, created = Like.objects.get_or_create(user=request.user, member=m)
        if not created: obj.delete()
        elif m.user_id:
            notify_like(request.user, me(request), m)
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
    def get_default_redirect_url(self):
        # members land on their own dashboard, staff on the admin dashboard
        return reverse("dashboard" if self.request.user.is_staff else "m_dashboard")

def signup(request):
    if request.user.is_authenticated: return redirect("dashboard" if request.user.is_staff else "m_dashboard")
    form = SignupForm(request.POST or None)
    if form.is_valid():
        user = form.save(); login(request, user)
        messages.success(request, "Karibu Sakinah! Complete your profile so others can get to know you.")
        return redirect(safe_next(request) or "m_profile_edit")
    return render(request, "registration/signup.html", {"form": form, "next": safe_next(request) or "", "faces": faces()})

@login_required
def profile_edit(request):
    if me(request) and not request.user.is_staff: return redirect("m_profile_edit")   # members edit inside their dashboard
    # user_id (not user=) so request.user.member stays unset until the profile is saved
    m = me(request) or Member(user_id=request.user.pk, name=request.user.get_full_name() or request.user.username, age=18)
    form = ProfileForm(request.POST or None, request.FILES or None, instance=m)
    if form.is_valid():
        form.save(); messages.success(request, "Profile saved.")
        return redirect("member", pk=form.instance.pk)
    return render(request, "profile_edit.html", {"form": form})

EMOJI = "😊 🙂 😄 🤲 🙏 ❤️ 🌸 🌙 ⭐ 👍 👋 🤝 💐 😇 🕌 📿".split()

def thread_qs(user, mine, other):
    q = Q(sender=user, to=other)
    if other.user_id and mine: q |= Q(sender=other.user, to=mine)
    return Message.objects.filter(q).select_related("sender").order_by("created")

def mark_groups(msgs, prev=None):
    """Flag which messages start a new day or a new run from the same person, so the chat is grouped like a messenger."""
    for m in msgs:
        m.show_day = prev is None or timezone.localtime(m.created).date() != timezone.localtime(prev.created).date()
        m.show_av = prev is None or prev.sender_id != m.sender_id or m.show_day
        prev = m
    return msgs

def conversation_rows(user, mine):
    """One row per person: the other member, the last message, and how many of their messages are still unread."""
    rows = {}
    q = Q(sender=user) | (Q(to=mine) if mine else Q(pk__in=[]))
    for msg in Message.objects.filter(q).select_related("to", "sender__member").order_by("-created"):
        other = msg.to if msg.sender_id == user.id else getattr(msg.sender, "member", None)
        if other is None or (mine and other.pk == mine.pk): continue
        row = rows.setdefault(other.pk, {"member": other, "last": msg, "unread": 0})
        if mine and msg.to_id == mine.pk and not msg.read: row["unread"] += 1
    return list(rows.values())

def call_why(mine, other, ok, reason):
    """Why the call buttons are off, in Swahili, so the chat can say it instead of hiding them."""
    if ok or reason == "premium": return ""
    if mine is None: return "Kamilisha wasifu wako ili uweze kupiga simu."
    if reason == "spent": return "Umetumia muda wako wote wa simu leo. Utapata mwingine baada ya masaa 24, au ongeza kifurushi."
    if not other.user_id: return f"{other.first_name} bado hajaanza kutumia simu za Sakinah."
    if reason.startswith("You can't call"): return "Huwezi kumpigia simu mwanachama huyu."
    return "Simu haipatikani kwa akaunti hii kwa sasa."


def call_block_en(mine):
    """The same, in English, for the pages that are written in English."""
    from members.views import call_block_en as en
    return "premium" if mine and mine.allowance("daily_call_seconds") == 0 else en(mine)

def call_block(mine):
    """Why this member may not place a call right now, in Swahili, or "" when they may."""
    if mine is None: return "Kamilisha wasifu wako ili uweze kupiga simu."
    if mine.allowance("daily_call_seconds") == 0: return "premium"
    if mine.call_seconds_left == 0:
        return "Umetumia muda wako wote wa simu leo. Utapata mwingine baada ya masaa 24, au ongeza kifurushi."
    return ""

def message_block(mine, other=None):
    """Why this member may not write right now, in Swahili, or "" when they may.

    A plan buys the right to start a conversation and to keep writing in it. Without one you may
    still answer whoever wrote to you, one answer for each message they send.
    """
    if mine is None: return "Kamilisha wasifu wako ili uweze kutuma ujumbe."
    has_plan = mine.allowance("daily_messages") != 0
    sent, got = Message.thread_counts(mine.user, other) if other is not None else (0, 0)
    if other is not None and (sent or got):                       # the conversation is already going
        if has_plan or sent < got: return ""
        return f"Umeshajibu ujumbe wake. Subiri {other.first_name} akuandikie tena, au jiunge na kifurushi ili uandike wakati wowote."
    if not has_plan:
        return "Kifurushi chako hakikuruhusu kuanzisha mazungumzo. Jiunge na kifurushi ili uanze; kujibu aliyekuandikia ni bure."
    if mine.messages_left == 0:
        return "Umefikia kikomo cha mazungumzo mapya ya leo. Utaweza kuanzisha mengine baada ya masaa 24, au ongeza kifurushi."
    return ""

def chat_page(request, other=None, form=None):
    """The messages screen: the conversation list on the left and, when one is picked, the chat on the right."""
    from members.calls import call_permission
    mine = me(request)
    blocked = liked_blocked(request.user)
    rows = [c for c in conversation_rows(request.user, mine) if c["member"].pk not in blocked]
    q = (request.GET.get("q") or "").strip()
    shown = [c for c in rows if q.lower() in c["member"].name.lower() or q.lower() in c["last"].preview.lower()] if q else rows
    today = timezone.localdate()
    ctx = {"convos": shown, "other": other, "f": request.GET, "n_unread": sum(c["unread"] for c in rows), "emoji": EMOJI,
           "today": today, "yesterday": today - timedelta(days=1), "blocked_ids": blocked, "me_member": mine}
    if other:
        they_blocked_me = bool(other.user_id and mine and Block.objects.filter(user=other.user, member=mine).exists())
        no_send = message_block(mine, other)
        can_send = other.pk not in blocked and not they_blocked_me and other.can_message(mine) and not no_send
        call_ok, call_reason = call_permission(mine, other) if mine else (False, "")
        msgs = mark_groups(list(thread_qs(request.user, mine, other)))
        ctx.update({"msgs": msgs, "form": form or ConversationForm(), "can_send": can_send, "call_ok": call_ok, "call_reason": call_reason, "call_why": call_why(mine, other, call_ok, call_reason),
                    "they_blocked_me": they_blocked_me, "last_id": msgs[-1].pk if msgs else 0, "no_send": no_send,
                    "msgs_left": mine.messages_left if mine else 0})
    return render(request, "messages.html", ctx)

def liked_blocked(user):
    return set(Block.objects.filter(user=user).values_list("member_id", flat=True))

@login_required
def thread(request, pk):
    other, mine = get_object_or_404(Member, pk=pk), me(request)
    if mine and other.pk == mine.pk: return redirect("inbox")
    form = None
    if request.method == "POST":
        form = ConversationForm(request.POST, request.FILES)
        blocked = liked_blocked(request.user)
        they_blocked_me = bool(other.user_id and mine and Block.objects.filter(user=other.user, member=mine).exists())
        if other.pk in blocked or they_blocked_me:
            messages.error(request, "Huwezi kumtumia ujumbe mwanachama huyu.")
        elif not other.can_message(mine):
            messages.error(request, f"{other.first_name} anapokea ujumbe kutoka kwa {other.get_allow_messages_from_display().lower()} pekee.")
        elif message_block(mine, other):
            messages.error(request, message_block(mine, other))
        elif form.is_valid():
            d = form.cleaned_data
            Message.objects.create(sender=request.user, to=other, body=d["body"], image=d.get("image"), audio=d.get("voice"),
                                   duration=min(d.get("duration") or 0, 120) if d.get("voice") else 0,
                                   opens=Message.starts_conversation(request.user, other))
            if other.user_id and other.notify_messages and mine:
                Notification.objects.create(user=other.user, title=f"Ujumbe mpya kutoka {mine.name}", link=reverse("thread", args=[mine.pk]))
            if request.headers.get("x-requested-with") == "fetch": return JsonResponse({"ok": True})
            return redirect("thread", pk=pk)
        if request.headers.get("x-requested-with") == "fetch":
            errs = [str(m) for m in messages.get_messages(request)] + [e for v in form.errors.values() for e in v]
            return JsonResponse({"ok": False, "error": errs[0] if errs else "Ujumbe haukutumwa."}, status=400)
    if mine and other.user_id: Message.objects.filter(sender=other.user, to=mine, read=False).update(read=True)
    return chat_page(request, other, form)

@login_required
def thread_feed(request, pk):
    """New messages since ?after=, so an open chat updates itself without reloading the page."""
    other, mine = get_object_or_404(Member, pk=pk), me(request)
    after = int(request.GET.get("after") or 0) if (request.GET.get("after") or "0").isdigit() else 0
    before = thread_qs(request.user, mine, other).filter(pk__lte=after).last() if after else None
    msgs = mark_groups(list(thread_qs(request.user, mine, other).filter(pk__gt=after)[:50]), before)
    if mine and other.user_id: Message.objects.filter(sender=other.user, to=mine, read=False).update(read=True)
    today = timezone.localdate()
    html = "".join(render_to_string("partials/chat_msg.html", {"msg": m, "other": other, "user": request.user,
                                                               "today": today, "yesterday": today - timedelta(days=1)}, request) for m in msgs)
    seen = bool(mine) and Message.objects.filter(sender=request.user, to=other, read=False).count() == 0
    return JsonResponse({"html": html, "last": msgs[-1].pk if msgs else after, "online": other.is_online, "seen": seen})

@login_required
def inbox(request):
    return chat_page(request)

@login_required
def notifications(request):
    notes = list(request.user.notifications.all()[:50])
    request.user.notifications.filter(read=False).update(read=True)
    return render(request, "notifications.html", {"notes": notes})
