import json
from datetime import date, timedelta
from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.sessions.models import Session
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from core.forms import LOCATIONS
from core.models import (Block, ConversationState, Event, EventCategory, EventRegistration, EventSave, Like, Member, MemberPhoto,
                         Message, Notification, Payment, Plan, PremiumPerk, ProfileView, SearchLog, Shortlist, SiteSetting, SupportTicket)
from core.views import safe_next
from . import data
from .forms import (AccountForm, ConversationForm, MemberProfileForm, PaymentRequestForm, PhotoForm, PreferencesForm, PrivacyForm, ProfileSettingsForm, SettingsPrefsForm,
                    TicketForm, NotifyForm, AppearanceForm)

AGES = [("18", "18"), ("20", "20"), ("25", "25"), ("30", "30"), ("35", "35"), ("40", "40"), ("45", "45"), ("50", "50"), ("60", "60+")]

def me_or_create(request):
    m = getattr(request.user, "member", None)
    if m is None:
        m = Member.objects.create(user=request.user, name=request.user.get_full_name() or request.user.get_username(), age=18, gender="M",
                                  city=LOCATIONS[0], occupation="")
    return m

def page(request, template, ctx, nav, **opts):
    me = ctx.get("me") or me_or_create(request)
    base = {"site": SiteSetting.load(), "me": me, "nav": nav, "header_nav": opts.get("header", "main"), **data.counts(request.user, me)}
    base.update({k: v for k, v in opts.items() if k != "header"})
    return render(request, template, {**base, **ctx})

def decorate(members, request, me):
    """Attach the flags member cards need (liked by me, mutual, photo visible) without extra queries per card."""
    members = list(members)
    liked = set(request.user.likes.values_list("member_id", flat=True))
    liked_me = set(data.liked_me(me).values_list("pk", flat=True))
    for m in members:
        m.i_liked, m.likes_me = m.pk in liked, m.pk in liked_me
        m.is_mutual = m.i_liked and m.likes_me
        rule = m.photo_visibility
        m.can_see_photo = rule == "all" or (rule == "verified" and me.verified) or (rule == "premium" and me.is_premium)
    return members

def visible(qs, request, me):
    qs = qs.exclude(pk=me.pk).exclude(pk__in=data.blocked_ids(request.user)).exclude(profile_visibility="hidden")
    if me.user_id: qs = qs.exclude(user__blocks__member=me)        # people who blocked me
    if not me.verified: qs = qs.exclude(profile_visibility="verified")
    if not me.is_premium: qs = qs.exclude(profile_visibility="premium")
    return qs

def tab_counts(**qs): return {k: v.count() for k, v in qs.items()}

# ---------- dashboard ----------
@login_required
def dashboard(request):
    me = me_or_create(request)
    comp = data.completion(me)
    acts = [("heart", "People who liked you", data.liked_me(me).count(), "m_liked"), ("eye", "Profile views", me.profile_views.count(), "m_views"),
            ("chat", "New messages", Message.objects.filter(to=me, read=False).count(), "m_messages"),
            ("people", "Mutual matches", data.mutual(request.user, me).count(), "m_matches"),
            ("bell", "New notifications", request.user.notifications.filter(read=False).count(), "m_notifications")]
    perks = list(PremiumPerk.objects.all()[:6])
    return page(request, "members/dashboard.html", {"me": me, "comp": comp, "acts": acts, "perks": perks,
        "suggested": decorate(data.suggestions(request.user, me, 8), request, me),
        "events": Event.objects.filter(date__gte=date.today()).order_by("date")[:3]}, "dashboard", header="notify", hide_events_nav=True)

# ---------- find a match ----------
@login_required
def find(request):
    me, g = me_or_create(request), request.GET
    seek = g.get("seek") or ("F" if me.gender == "M" else "M")
    qs = visible(Member.objects.filter(show_in_search=True), request, me).filter(gender=seek)
    a_min = int(g.get("age_min") or me.pref_age_min or 20); a_max = int(g.get("age_max") or me.pref_age_max or 40)
    qs = qs.filter(age__gte=a_min, age__lte=a_max if a_max < 60 else 120)
    if g.get("q"):
        q = g["q"].strip()
        qs = qs.filter(Q(name__icontains=q) | Q(city__icontains=q) | Q(occupation__icontains=q) | Q(age=q) if q.isdigit() else
                       Q(name__icontains=q) | Q(city__icontains=q) | Q(occupation__icontains=q) | Q(education__icontains=q))
    for key, field in [("city", "city"), ("marital", "marital_status"), ("practice", "practice"), ("body", "body_type")]:
        if g.get(key): qs = qs.filter(**{field: g[key]})
    if g.get("education"): qs = qs.filter(education__icontains=g["education"])
    if g.get("profession"): qs = qs.filter(occupation__icontains=g["profession"])
    if g.get("photo") == "1": qs = qs.exclude(photo="")
    if g.get("verified") == "1": qs = qs.filter(verified=True)
    if g.get("online") == "1": qs = qs.filter(show_online=True, last_seen__gte=timezone.now() - timedelta(minutes=5))
    sort = g.get("sort", "newest")
    qs = qs.order_by({"newest": "-joined", "age": "age", "compat": "-compatibility", "active": "-last_seen"}.get(sort, "-joined"), "pk")
    if "page" not in g and any(g.get(k) for k in ("q", "city", "marital", "education", "profession", "practice", "body", "age_min")):
        parts = ([f"\u201c{g['q']}\u201d"] if g.get("q") else []) + [f"{g.get('age_min')}-{g.get('age_max', '')} yrs"] * bool(g.get("age_min"))
        parts += [dict(Member.MARITAL + Member.PRACTICE).get(g[k], g[k]) for k in ("city", "marital", "education", "profession", "practice", "body") if g.get(k)]
        SearchLog.objects.create(user=request.user, results=qs.count(), summary=", ".join(parts)[:200])
    pg = Paginator(qs, 20).get_page(g.get("page"))
    params = g.copy(); params.pop("page", None)
    return page(request, "members/find.html", {"me": me, "page": pg, "members": decorate(pg.object_list, request, me), "f": g, "seek": seek,
        "a_min": a_min, "a_max": a_max, "locations": LOCATIONS, "marital": Member.MARITAL, "practice": Member.PRACTICE,
        "educations": ["Primary", "Secondary", "Certificate", "Diploma", "Bachelor", "Master", "PhD"],
        "professions": sorted(set(Member.objects.exclude(occupation="").values_list("occupation", flat=True)))[:40],
        "bodies": ["Slim", "Average", "Athletic", "Heavy"], "qs": params.urlencode(), "view": g.get("view", "grid"), "sort": sort,
        "pages": pg.paginator.get_elided_page_range(pg.number, on_each_side=2, on_ends=1)}, "find", no_sidebar=True, no_search=True)

# ---------- my matches ----------
MATCH_TABS = [("all", "All Matches"), ("mutual", "Mutual Matches"), ("liked_you", "People Who Liked You"), ("you_liked", "You Liked"), ("shortlisted", "Shortlisted")]

@login_required
def matches(request):
    me, g = me_or_create(request), request.GET
    sets = {"all": data.all_matches(request.user, me), "mutual": data.mutual(request.user, me), "liked_you": data.liked_me(me),
            "you_liked": data.i_liked(request.user), "shortlisted": Member.objects.filter(shortlisted_by__user=request.user)}
    n = tab_counts(**sets)
    tab = g.get("tab") if g.get("tab") in sets else "all"
    qs = sets[tab].exclude(pk__in=data.blocked_ids(request.user))
    if g.get("show") == "online": qs = qs.filter(show_online=True, last_seen__gte=timezone.now() - timedelta(minutes=5))
    if g.get("show") == "verified": qs = qs.filter(verified=True)
    if g.get("city"): qs = qs.filter(city=g["city"])
    if g.get("q"): qs = qs.filter(Q(name__icontains=g["q"]) | Q(city__icontains=g["q"]) | Q(occupation__icontains=g["q"]))
    qs = qs.order_by("joined" if g.get("sort") == "oldest" else "-joined")
    return page(request, "members/matches.html", {"me": me, "members": decorate(qs, request, me), "tabs": [(k, l, n[k]) for k, l in MATCH_TABS],
        "tab": tab, "n": n, "f": g, "locations": LOCATIONS}, "matches", header="notify")

# ---------- messages ----------
def conversations(user, me):
    """One row per person: last message, unread count and favourite/archived flags."""
    convos = {}
    q = Q(sender=user) | Q(to=me)
    for msg in Message.objects.filter(q).select_related("to", "sender__member").order_by("-created"):
        other = msg.to if msg.sender_id == user.id else getattr(msg.sender, "member", None)
        if other is None or other == me: continue
        c = convos.setdefault(other.pk, {"member": other, "last": msg, "unread": 0})
        if msg.to_id == me.pk and not msg.read: c["unread"] += 1
    states = {s.member_id: s for s in ConversationState.objects.filter(user=user)}
    for pk, c in convos.items():
        s = states.get(pk); c["fav"], c["archived"] = (s.favorite, s.archived) if s else (False, False)
    return list(convos.values())

@login_required
def messages_page(request, pk=None):
    me, g = me_or_create(request), request.GET
    blocked = data.blocked_ids(request.user)
    if pk and request.method == "GET":       # opening a chat marks it read before the list counts are built
        Message.objects.filter(sender__member__pk=pk, to=me, read=False).update(read=True)
    allc = [c for c in conversations(request.user, me) if c["member"].pk not in blocked]
    tab = g.get("tab", "all")
    shown = {"all": [c for c in allc if not c["archived"]], "unread": [c for c in allc if c["unread"] and not c["archived"]],
             "favorites": [c for c in allc if c["fav"]], "archived": [c for c in allc if c["archived"]]}.get(tab, allc)
    if g.get("q"):
        q = g["q"].lower(); shown = [c for c in shown if q in c["member"].name.lower() or q in c["last"].body.lower()]
    other = get_object_or_404(Member, pk=pk) if pk else (shown[0]["member"] if shown else None)
    form = ConversationForm(request.POST or None, request.FILES or None)
    if other and request.method == "POST":
        if other.pk in blocked or (other.user_id and Block.objects.filter(user=other.user, member=me).exists()):
            messages.error(request, "You can't message this member.")
        elif not other.can_message(me):
            messages.error(request, f"{other.name} only accepts messages from {other.get_allow_messages_from_display().lower()}.")
        elif form.is_valid():
            Message.objects.create(sender=request.user, to=other, body=form.cleaned_data["body"], image=form.cleaned_data.get("image"))
            if other.user_id and other.notify_messages:
                Notification.objects.create(user=other.user, title=f"New message from {me.name}", link=reverse("m_messages_with", args=[me.pk]))
            return redirect("m_messages_with", pk=other.pk)
    thread = []
    if other:
        thread = Message.objects.filter(Q(sender=request.user, to=other) | (Q(sender=other.user, to=me) if other.user_id else Q(pk__in=[]))).order_by("created")
    state = ConversationState.objects.filter(user=request.user, member=other).first() if other else None
    return page(request, "members/messages.html", {"me": me, "convos": shown, "other": other, "thread": thread, "form": form, "tab": tab, "f": g,
        "n_all": len([c for c in allc if not c["archived"]]), "n_unread": sum(1 for c in allc if c["unread"]), "state": state,
        "can_send": bool(other) and other.pk not in blocked and other.can_message(me),
        "emoji": "😊 🙂 😄 🤲 🙏 ❤️ 🌸 🌙 ⭐ 👍 👋 🤝 💐 😇 🕌 📿".split(), "blocked_ids": blocked,
        "today": timezone.localdate(), "yesterday": timezone.localdate() - timedelta(days=1)}, "messages")

@login_required
@require_POST
def conversation_action(request, pk):
    other = get_object_or_404(Member, pk=pk)
    s, _ = ConversationState.objects.get_or_create(user=request.user, member=other)
    act = request.POST.get("act")
    if act == "fav": s.favorite = not s.favorite
    elif act == "archive": s.archived = not s.archived
    s.save()
    return redirect(safe_next(request) or reverse("m_messages_with", args=[pk]))

# ---------- my profile ----------
@login_required
def profile(request):
    me = me_or_create(request)
    n_photos = (1 if me.photo else 0) + me.photos.count()
    return page(request, "members/profile.html", {"me": me, "comp": data.completion(me), "photos": me.photos.all()[:5], "tab": "overview",
        "n_photos": min(n_photos, 6), "empty_slots": range(max(0, 6 - n_photos)),
        "visibility_choices": [("all", "Show my profile to all members"), ("verified", "Show only to verified members"),
                               ("premium", "Show only to premium members"), ("hidden", "Hide my profile")]}, "profile")

@login_required
def profile_edit(request):
    me = me_or_create(request)
    form = MemberProfileForm(request.POST or None, instance=me)
    if form.is_valid():
        form.save(); messages.success(request, "Profile saved.")
        return redirect("m_profile")
    return page(request, "members/profile_edit.html", {"me": me, "form": form, "tab": "edit"}, "profile")

@login_required
def photos(request):
    me = me_or_create(request)
    form = PhotoForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if (1 if me.photo else 0) + me.photos.count() >= 6:
            messages.error(request, "You can have up to 6 photos. Remove one first.")
        elif form.is_valid():
            if not me.photo: me.photo = form.cleaned_data["image"]; me.save(update_fields=["photo"])
            else: MemberPhoto.objects.create(member=me, image=form.cleaned_data["image"], order=me.photos.count() + 2)
            messages.success(request, "Photo added.")
            return redirect(safe_next(request) or "m_photos")
    return page(request, "members/photos.html", {"me": me, "form": form, "photos": me.photos.all(), "tab": "photos",
        "n_photos": (1 if me.photo else 0) + me.photos.count()}, "profile")

@login_required
@require_POST
def photo_action(request, pk=None):
    me = me_or_create(request)
    act = request.POST.get("act")
    if pk is None:          # the main photo
        if act == "delete" and me.photo:
            nxt = me.photos.first()
            me.photo = nxt.image if nxt else ""; me.save(update_fields=["photo"])
            if nxt: nxt.delete()
    else:
        p = get_object_or_404(MemberPhoto, pk=pk, member=me)
        if act == "delete": p.delete()
        elif act == "main":
            old = me.photo; me.photo = p.image; me.save(update_fields=["photo"])
            if old: p.image = old; p.save(update_fields=["image"])
            else: p.delete()
    return redirect(safe_next(request) or "m_photos")

@login_required
def preferences(request):
    me = me_or_create(request)
    form = PreferencesForm(request.POST or None, instance=me)
    if form.is_valid(): form.save(); messages.success(request, "Partner preferences saved."); return redirect(safe_next(request) or "m_prefs")
    return page(request, "members/preferences.html", {"me": me, "form": form, "tab": "prefs"}, "profile")

@login_required
def verification(request):
    me = me_or_create(request)
    form = TicketForm(request.POST or None, request.FILES or None, initial={"subject": "Please verify my profile"})
    pending = SupportTicket.objects.filter(user=request.user, kind="verification", status="open").first()
    if request.method == "POST" and form.is_valid() and not form.cleaned_data.get("attachment"):
        form.add_error("attachment", "Attach a photo of your ID so we can verify you.")
    if request.method == "POST" and form.is_valid() and not me.verified and not pending:
        t = form.save(commit=False); t.user, t.kind = request.user, "verification"; t.save()
        messages.success(request, "Verification request sent. Our team will review it soon.")
        return redirect("m_verify")
    return page(request, "members/verification.html", {"me": me, "form": form, "pending": pending, "tab": "verify"}, "profile")

@login_required
@require_POST
def visibility(request):
    me = me_or_create(request)
    v = request.POST.get("profile_visibility")
    if v in dict(Member.VISIBILITY):
        me.profile_visibility = v; me.save(update_fields=["profile_visibility"]); messages.success(request, "Profile visibility updated.")
    return redirect(safe_next(request) or "m_profile")

# ---------- profile views ----------
AGE_OPTS = [("18-24", "18 - 24"), ("25-29", "25 - 29"), ("30-34", "30 - 34"), ("35-39", "35 - 39"), ("40-49", "40 - 49"), ("50-99", "50+")]

def age_range(g):
    return next(((int(a.split("-")[0]), int(a.split("-")[1])) for a, _ in AGE_OPTS if a == g.get("age")), None)

@login_required
def views(request):
    me, g = me_or_create(request), request.GET
    base = me.profile_views.exclude(viewer=request.user).exclude(viewer__member__in=data.blocked_ids(request.user))
    tab = g.get("tab", "all")
    qs = data.period_filter(base, "created", {"recent": "7", "month": "month", "90": "90"}.get(tab, ""))
    rows = (qs.values("viewer").annotate(last=Max("created"), n=Count("id")).order_by("-last"))
    viewers = {m.user_id: m for m in Member.objects.filter(user__in=[r["viewer"] for r in rows])}
    if g.get("show") == "verified": viewers = {k: v for k, v in viewers.items() if v.verified}
    if g.get("show") == "premium": viewers = {k: v for k, v in viewers.items() if v.is_premium}
    if g.get("city"): viewers = {k: v for k, v in viewers.items() if v.city == g["city"]}
    if age_range(g):
        lo, hi = age_range(g); viewers = {k: v for k, v in viewers.items() if lo <= v.age <= hi}
    items = []
    for r in rows:
        m = viewers.get(r["viewer"])
        if m: m.viewed_at, m.view_count = r["last"], r["n"]; items.append(m)
    now = timezone.now()
    summary = [("eye", "Total Profile Views", base.count()), ("cal", "This Week", data.period_filter(base, "created", "7").count()),
               ("cal", "This Month", data.period_filter(base, "created", "month").count()), ("cal", "Last 3 Months", data.period_filter(base, "created", "90").count()),
               ("people", "Unique Visitors", base.values("viewer").distinct().count())]
    top = sorted([m for m in Member.objects.filter(user__in=base.values("viewer"))], key=lambda m: -base.filter(viewer=m.user).count())[:5]
    for m in top: m.view_count = base.filter(viewer=m.user).count()
    return page(request, "members/views.html", {"me": me, "members": decorate(items, request, me), "tab": tab, "f": g, "summary": summary, "top": top,
        "tabs": [("all", "All Views", base.count(), "eye"), ("recent", "Recent (7 days)", data.period_filter(base, "created", "7").count(), "cal"),
                 ("month", "This Month", data.period_filter(base, "created", "month").count(), "cal"), ("90", "Last 3 Months", data.period_filter(base, "created", "90").count(), "cal")],
        "locations": LOCATIONS, "age_opts": AGE_OPTS, "now": now}, "views", header="notify")

# ---------- who liked me ----------
@login_required
def liked(request):
    me, g = me_or_create(request), request.GET
    base = Like.objects.filter(member=me).exclude(user=request.user).exclude(user__member__in=data.blocked_ids(request.user)).select_related("user__member")
    seen = me.likes_seen_at
    new = base.filter(created__gt=seen) if seen else base
    tab = g.get("tab", "all")
    qs = {"new": new, "week": data.period_filter(base, "created", "7"), "month": data.period_filter(base, "created", "month")}.get(tab, base)
    if g.get("show") == "verified": qs = qs.filter(user__member__verified=True)
    if g.get("city"): qs = qs.filter(user__member__city=g["city"])
    if age_range(g):
        lo, hi = age_range(g); qs = qs.filter(user__member__age__gte=lo, user__member__age__lte=hi)
    qs = qs.order_by("created" if g.get("sort") == "oldest" else "-created")
    items = []
    for lk in qs:
        m = getattr(lk.user, "member", None)
        if m: m.liked_at = lk.created; items.append(m)
    n = {"all": base.count(), "new": new.count(), "week": data.period_filter(base, "created", "7").count(), "month": data.period_filter(base, "created", "month").count()}
    resp = page(request, "members/liked.html", {"me": me, "members": decorate(items, request, me), "tab": tab, "n": n, "f": g, "locations": LOCATIONS, "age_opts": AGE_OPTS,
        "locked": not me.is_premium, "perks": ["See who liked you", "Get more profile views", "Priority in search results", "Advanced filters"]}, "liked")
    if me.is_premium:
        me.likes_seen_at = timezone.now(); me.save(update_fields=["likes_seen_at"])
    return resp

# ---------- my activities ----------
def activity_feed(user, me, kind="all", limit=40):
    items = []
    if kind in ("all", "views"):
        for v in me.profile_views.exclude(viewer=user).select_related("viewer__member")[:limit]:
            m = getattr(v.viewer, "member", None)
            if m: items.append({"t": v.created, "kind": "view", "icon": "eye", "color": "#2563eb", "m": m, "text": "viewed your profile"})
    if kind in ("all", "likes"):
        for lk in Like.objects.filter(member=me).exclude(user=user).select_related("user__member")[:limit]:
            m = getattr(lk.user, "member", None)
            if m: items.append({"t": lk.created, "kind": "like", "icon": "heart", "color": "#d61f45", "m": m, "text": "liked your profile"})
    if kind in ("all", "matches"):
        mutual_ids = set(data.mutual(user, me).values_list("pk", flat=True))
        for lk in Like.objects.filter(user=user, member__in=mutual_ids).select_related("member"):
            back = Like.objects.filter(user=lk.member.user, member=me).first()
            t = max(lk.created, back.created) if back else lk.created
            items.append({"t": t, "kind": "match", "icon": "people", "color": "#2b4fb8", "m": lk.member, "text": "mutual", "pre": "You got a"})
    if kind in ("all", "messages"):
        for msg in Message.objects.filter(to=me).select_related("sender__member")[:limit]:
            m = getattr(msg.sender, "member", None)
            if m: items.append({"t": msg.created, "kind": "message", "icon": "chat", "color": "#2b6ed9", "m": m, "text": "sent you a message", "quote": msg.body[:40]})
    if kind in ("all", "saved"):
        for s in Shortlist.objects.filter(user=user).select_related("member")[:limit]:
            items.append({"t": s.created, "kind": "saved", "icon": "bookmark", "color": "#1e3a8a", "m": s.member, "text": "saved", "pre": "You saved"})
    if kind in ("all", "search"):
        for s in SearchLog.objects.filter(user=user)[:limit]:
            items.append({"t": s.created, "kind": "search", "icon": "search", "color": "#0f5a39", "m": None, "text": s.summary or "All members", "n": s.results})
    return sorted(items, key=lambda i: i["t"], reverse=True)[:limit]

def nice_ticks(top):
    """Five evenly spaced y-axis labels (top first) for the activity bar chart."""
    step = max(1, -(-top // 4))
    return [step * i for i in range(4, -1, -1)]

@login_required
def activity(request):
    me = me_or_create(request)
    tab = request.GET.get("tab", "all")
    week = timezone.now() - timedelta(days=7); prev = week - timedelta(days=7)
    def wk(qs, f="created"):
        a = qs.filter(**{f"{f}__gte": week}).count(); b = qs.filter(**{f"{f}__gte": prev, f"{f}__lt": week}).count()
        return round((a - b) * 100 / b) if b else (100 if a else 0)
    views_qs, likes_qs = me.profile_views.exclude(viewer=request.user), Like.objects.filter(member=me).exclude(user=request.user)
    msgs_qs, saved_qs = Message.objects.filter(to=me), Shortlist.objects.filter(user=request.user)
    n_mutual = data.mutual(request.user, me).count()
    cards = [("eye", "Profile Views", views_qs.count(), wk(views_qs), "pink", "#a0123c"), ("heart", "People Who Liked Me", likes_qs.count(), wk(likes_qs), "grn", "#0f7a45"),
             ("people", "Mutual Matches", n_mutual, None, "blu", "#2b4fb8"), ("chat", "New Messages", msgs_qs.filter(read=False).count(), wk(msgs_qs), "yel", "#b8741a"),
             ("bookmark", "Saved Profiles", saved_qs.count(), wk(saved_qs), "pur", "#7c3aed")]
    month = timezone.now() - timedelta(days=30)
    bars = [("Profile Views", views_qs.filter(created__gte=month).count(), "#a0123c"), ("Likes", likes_qs.filter(created__gte=month).count(), "#f472b6"),
            ("Matches", n_mutual, "#16a34a"), ("Messages", msgs_qs.filter(created__gte=month).count(), "#3b82f6"), ("Saved", saved_qs.filter(created__gte=month).count(), "#8b5cf6")]
    top_n = nice_ticks(max([b[1] for b in bars] + [1]))[0]
    bars = [{"label": l, "n": n, "h": round(n * 100 / top_n), "c": c} for l, n, c in bars]
    scores = {}
    for v in views_qs.values("viewer__member").annotate(n=Count("id")): scores.setdefault(v["viewer__member"], {"views": 0, "likes": 0, "msgs": 0})["views"] = v["n"]
    for v in likes_qs.values("user__member").annotate(n=Count("id")): scores.setdefault(v["user__member"], {"views": 0, "likes": 0, "msgs": 0})["likes"] = v["n"]
    for v in msgs_qs.values("sender__member").annotate(n=Count("id")): scores.setdefault(v["sender__member"], {"views": 0, "likes": 0, "msgs": 0})["msgs"] = v["n"]
    scores.pop(None, None)
    top = sorted(scores.items(), key=lambda kv: -(kv[1]["views"] + 2 * kv[1]["likes"] + 3 * kv[1]["msgs"]))[:5]
    tops = []
    for pk, s in top:
        m = Member.objects.filter(pk=pk).first()
        if not m: continue
        best = max(("views", "eye", "view"), ("likes", "heart", "like"), ("msgs", "chat", "message"), key=lambda k: s[k[0]])
        m.top_icon, m.top_text = best[1], f"{s[best[0]]} {best[2]}{'s' if s[best[0]] != 1 else ''}"
        tops.append(m)
    tabs = [("all", "All Activities"), ("views", "Profile Views"), ("likes", "Likes"), ("matches", "Matches"), ("messages", "Messages"), ("saved", "Saved Profiles"), ("search", "Search Activity")]
    feed = Paginator(activity_feed(request.user, me, tab, limit=80), 8).get_page(request.GET.get("page"))
    return page(request, "members/activity.html", {"me": me, "cards": cards, "feed": feed, "tab": tab, "tabs": tabs,
        "bars": bars, "ticks": nice_ticks(top_n), "tops": tops}, "activity")

# ---------- events ----------
@login_required
def events(request):
    me, g = me_or_create(request), request.GET
    today = date.today()
    tab = g.get("tab", "all")
    qs = Event.objects.select_related("category").annotate(reg_count=Count("registrations"))
    mine_ids = set(EventRegistration.objects.filter(user=request.user).values_list("event_id", flat=True))
    qs = {"upcoming": qs.filter(date__gte=today), "mine": qs.filter(pk__in=mine_ids), "past": qs.filter(date__lt=today)}.get(tab, qs.filter(date__gte=today) if tab == "all" else qs)
    if g.get("q"): qs = qs.filter(Q(title__icontains=g["q"]) | Q(city__icontains=g["q"]) | Q(description__icontains=g["q"]) | Q(tags__icontains=g["q"]))
    if g.get("cat"): qs = qs.filter(category__slug=g["cat"])
    if g.get("city"): qs = qs.filter(city=g["city"])
    if g.get("type"): qs = qs.filter(tags__icontains=g["type"])
    qs = qs.order_by("-date" if tab == "past" else "date", "pk")
    import calendar as cal
    try: y, mth = map(int, g.get("month", "").split("-"))
    except ValueError:
        nxt = Event.objects.filter(date__gte=today).order_by("date").first(); y, mth = (nxt.date.year, nxt.date.month) if nxt else (today.year, today.month)
    days = {e.date.day: ("mine" if e.pk in mine_ids else "ev") for e in Event.objects.filter(date__year=y, date__month=mth)}
    prev_m = date(y - (mth == 1), 12 if mth == 1 else mth - 1, 1); next_m = date(y + (mth == 12), 1 if mth == 12 else mth + 1, 1)
    types = sorted({t for e in Event.objects.all() for t in e.tag_list})
    return page(request, "members/events.html", {"me": me, "events": qs, "tab": tab, "f": g, "mine": mine_ids,
        "saved": set(EventSave.objects.filter(user=request.user).values_list("event_id", flat=True)),
        "categories": EventCategory.objects.annotate(n=Count("events")).filter(n__gt=0).order_by("order", "pk"),
        "locations": sorted(set(Event.objects.values_list("city", flat=True))), "types": types,
        "cal": cal.Calendar(firstweekday=6).monthdayscalendar(y, mth), "cal_title": date(y, mth, 1), "cal_days": days,
        "today": today.day if (today.year, today.month) == (y, mth) else 0, "prev_month": prev_m.strftime("%Y-%m"), "next_month": next_m.strftime("%Y-%m"),
        "my_regs": EventRegistration.objects.filter(user=request.user).select_related("event").order_by("-event__date")[:3], "today_date": today},
        "events", search_hint="Search events, topics, locations...")

@login_required
def event_detail(request, pk):
    me = me_or_create(request)
    e = get_object_or_404(Event.objects.annotate(reg_count=Count("registrations")), pk=pk)
    return page(request, "members/event_detail.html", {"me": me, "e": e, "registered": EventRegistration.objects.filter(user=request.user, event=e).exists(),
        "saved": EventSave.objects.filter(user=request.user, event=e).exists(), "past": e.date < date.today()}, "events")

@login_required
@require_POST
def event_save(request, pk):
    e = get_object_or_404(Event, pk=pk)
    s, created = EventSave.objects.get_or_create(user=request.user, event=e)
    if not created: s.delete()
    return redirect(safe_next(request) or "m_events")

# ---------- membership ----------
PLAN_STYLE = ["basic", "silver", "gold", "platinum", "tanzanite"]

@login_required
def membership(request):
    me, tab = me_or_create(request), request.GET.get("tab", "plans")
    plans = list(Plan.objects.all())
    for i, p in enumerate(plans):   # style by name when it is one of the mockup tiers, otherwise by rank
        p.style = "ps-" + (p.name.lower() if p.name.lower() in PLAN_STYLE else PLAN_STYLE[min(i, 4)])
        p.icon_n = PLAN_STYLE.index(p.style[3:]) + 1
    form = PaymentRequestForm(request.POST or None, plans=plans, initial={"plan": request.GET.get("pay"), "phone": me.phone})
    free = next((p for p in plans if not p.price), plans[0] if plans else None)
    current = next((p for p in plans if me.is_premium and p.pk == me.plan_id), free)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        Payment.objects.create(user=request.user, payer_name=me.name, payer_phone=d["phone"], kind="premium", plan=d["plan"], months=d["months"],
            amount=d["plan"].price * d["months"], gateway=d["gateway"], reference=d["reference"], status="pending",
            description=f"{d['plan'].name} plan, {d['months']} month(s) (member request)")
        messages.success(request, "Asante! We received your payment details. Your plan will be activated once our team confirms the payment.")
        return redirect(reverse("m_membership") + "?tab=history")
    faq = [("How do I pay?", SiteSetting.load().payment_instructions),
           ("When is my plan activated?", "As soon as our team confirms your payment, usually within a few hours. You will get a notification."),
           ("Does my plan renew automatically?", "No. Plans do not renew automatically, so you are never charged without asking. Renew any time from this page."),
           ("Can I change my plan?", "Yes. Pay for the new plan and it starts after confirmation. Remaining time on a paid plan is kept.")]
    benefits = [("search", "Advanced Search", "Find matches with detailed preferences", "pink"), ("eye", "See Who Liked You", "Know who is interested in you", "grn"),
                ("chat", "Unlimited Messages", "Chat without limits", "blu"), ("star", "Featured Profile", "Get more visibility", "yel"),
                ("heart", "Priority in Search", "Appear at the top", "pur"), ("people", "Access to Premium Events", "Join exclusive events", "pink"),
                ("shield", "Verified Badge", "Build trust and credibility", "grn"), ("headset", "Dedicated Support", "Get priority assistance", "blu")]
    feats, included, prev = [], [], set()
    for p in plans:   # "All Gold features" means the plan includes everything the previous plan has
        own = {t for ok, t in p.feature_list if ok and not t.lower().startswith("all ")}
        inherits = any(ok and t.lower().startswith("all ") for ok, t in p.feature_list)
        prev = own | (prev if inherits else set()); included.append(prev)
        feats += [t for ok, t in p.feature_list if ok and t in own and t not in feats]
    compare = [(t, [t in inc for inc in included]) for t in feats]
    return page(request, "members/membership.html", {"me": me, "plans": plans, "tab": tab, "form": form, "faq": faq, "benefits": benefits,
        "history": Payment.objects.filter(user=request.user).select_related("plan"), "compare": compare, "show_pay": request.method == "POST" or "pay" in request.GET,
        "current": current, "prices": {str(p.pk): p.price for p in plans}, "pending": Payment.objects.filter(user=request.user, status="pending").select_related("plan").first()}, "membership", search_hint="Search members, events, topics...")

@login_required
def receipt(request, pk):
    return render(request, "dashboard/receipt.html", {"p": get_object_or_404(Payment.objects.select_related("plan"), pk=pk, user=request.user), "site": SiteSetting.load()})

# ---------- safety & privacy ----------
@login_required
def safety(request):
    me, tab = me_or_create(request), request.GET.get("tab", "overview")
    form = PrivacyForm(request.POST or None, instance=me)
    if request.method == "POST" and form.is_valid():
        form.save(); messages.success(request, "Privacy settings saved.")
        return redirect(reverse("m_safety") + (f"?tab={tab}" if tab != "overview" else ""))
    report = TicketForm(initial={"subject": request.GET.get("subject", "")})
    return page(request, "members/safety.html", {"me": me, "form": form, "tab": tab, "report": report,
        "blocked": Block.objects.filter(user=request.user).select_related("member")}, "safety")

@login_required
@require_POST
def block(request, pk):
    m = get_object_or_404(Member, pk=pk)
    me = me_or_create(request)
    if m == me: return redirect("m_safety")
    b, created = Block.objects.get_or_create(user=request.user, member=m)
    if not created: b.delete()
    messages.success(request, f"{m.name} {'blocked. They can no longer see or message you' if created else 'unblocked'}.")
    return redirect(safe_next(request) or reverse("m_safety") + "?tab=blocked")

# ---------- settings ----------
SETTINGS_FORMS = {"account": AccountForm, "profile": ProfileSettingsForm, "notify": NotifyForm, "prefs": SettingsPrefsForm, "look": AppearanceForm}

@login_required
def settings_page(request):
    me = me_or_create(request)
    section = request.POST.get("section")
    forms = {k: F(request.POST if section == k else None, request.FILES if section == k else None, instance=me, prefix=k) for k, F in SETTINGS_FORMS.items()}
    if section in forms and forms[section].is_valid():
        forms[section].save(); messages.success(request, "Settings saved.")
        return redirect(reverse("m_settings") + f"#{section}")
    others = 0
    for s in Session.objects.filter(expire_date__gte=timezone.now()):
        if s.get_decoded().get("_auth_user_id") == str(request.user.pk) and s.session_key != request.session.session_key: others += 1
    return page(request, "members/settings.html", {"me": me, "forms": forms, "tab": request.GET.get("tab", "account"), "other_sessions": others}, "settings")

@login_required
def password(request):
    me = me_or_create(request)
    form = PasswordChangeForm(request.user, request.POST or None)
    if form.is_valid():
        update_session_auth_hash(request, form.save()); messages.success(request, "Password changed.")
        return redirect("m_settings")
    return page(request, "members/password.html", {"me": me, "form": form}, "settings")

@login_required
@require_POST
def end_sessions(request):
    n = 0
    for s in Session.objects.filter(expire_date__gte=timezone.now()):
        if s.get_decoded().get("_auth_user_id") == str(request.user.pk) and s.session_key != request.session.session_key: s.delete(); n += 1
    messages.success(request, f"Logged out of {n} other session{'s' if n != 1 else ''}.")
    return redirect("m_settings")

@login_required
def export(request):
    me = me_or_create(request)
    skip = {"user", "plan", "photo", "last_seen", "likes_seen_at"}
    profile = {f.name: str(getattr(me, f.name)) for f in Member._meta.fields if f.name not in skip}
    payload = {"account": {"username": request.user.get_username(), "email": request.user.email, "joined": str(request.user.date_joined)},
               "profile": profile, "likes_given": [m.name for m in data.i_liked(request.user)],
               "messages_sent": [{"to": m.to.name, "at": str(m.created), "text": m.body} for m in Message.objects.filter(sender=request.user).select_related("to")],
               "event_registrations": [r.event.title for r in EventRegistration.objects.filter(user=request.user).select_related("event")],
               "payments": [{"invoice": p.invoice_no, "amount": p.amount, "status": p.status} for p in Payment.objects.filter(user=request.user)]}
    resp = HttpResponse(json.dumps(payload, indent=2, ensure_ascii=False), content_type="application/json")
    resp["Content-Disposition"] = 'attachment; filename="sakinah-my-data.json"'
    return resp

@login_required
@require_POST
def deactivate(request):
    me = me_or_create(request)
    if me.profile_visibility == "hidden":
        me.profile_visibility, me.show_in_search = "all", True; messages.success(request, "Welcome back! Your profile is visible again.")
    else:
        me.profile_visibility, me.show_in_search = "hidden", False; messages.success(request, "Your account is deactivated. Your profile is hidden until you reactivate it.")
    me.save(update_fields=["profile_visibility", "show_in_search"])
    return redirect("m_settings")

@login_required
@require_POST
def delete_account(request):
    if not request.user.check_password(request.POST.get("password", "")):
        messages.error(request, "Password is incorrect. Your account was not deleted."); return redirect(reverse("m_settings") + "#actions")
    if request.user.is_staff:
        messages.error(request, "Staff accounts can't be deleted here."); return redirect("m_settings")
    user = request.user; logout(request); user.delete()
    messages.success(request, "Your account and profile were deleted. Kwaheri.")
    return redirect("home")

# ---------- help & support ----------
FAQ = [("user", "#b4233f", "Getting Started", "Learn how to create an account, complete your profile and start searching.", [
          ("How do I start?", "Join free, complete your profile with a clear photo, set your partner preferences, then use Find a Match."),
          ("Is Sakinah free?", "Yes. Creating a profile, searching and sending likes are free. Premium plans add more features.")]),
       ("idcard", "#16a34a", "Profile & Verification", "How to verify your profile, upload photos and keep your account safe.", [
          ("How do I get verified?", "Go to My Profile > Verification and send a request with a photo of your ID. Our team reviews it."),
          ("How many photos can I add?", "Up to 6 photos. Use clear, recent and modest photos.")]),
       ("heart", "#d61f45", "Finding a Match", "Tips on using search filters, likes, messages and matches.", [
          ("What is a mutual match?", "When you like someone and they like you back, it becomes a mutual match."),
          ("Why can't I message someone?", "Some members only accept messages from verified or matched members. Check their profile.")]),
       ("star", "#c8902f", "Membership & Payments", "Information about membership plans, payments and benefits.", [
          ("How do I upgrade?", "Open Membership, choose a plan, pay by mobile money and enter the transaction reference."),
          ("Do plans renew automatically?", "No. You choose when to renew.")]),
       ("shield", "#16a34a", "Safety & Privacy", "How we protect your information and keep the community safe.", [
          ("Who can see my profile?", "You decide in Safety & Privacy: everyone, verified members, premium members, or hidden."),
          ("How do I block someone?", "Open their profile or conversation and choose Block. Manage blocked users in Safety & Privacy.")]),
       ("wrench", "#2563eb", "Technical Support", "Help with login, password, errors and other technical issues.", [
          ("I forgot my password", "Use 'Forgot password?' on the login page to get a reset link by email."),
          ("The site is not working", "Refresh the page or try another browser. If it continues, submit a ticket below.")]),
       ("people", "#d61f45", "Community Guidelines", "Our rules for a respectful and Islamic community.", [
          ("What is not allowed?", "Fake profiles, inappropriate photos, harassment, asking for money and sharing contact details too early."),
          ("What happens when I report someone?", "Our team reviews every report privately and may warn or remove the member.")])]

@login_required
def help_page(request):
    me = me_or_create(request)
    kind = request.POST.get("kind") or request.GET.get("kind") or "contact"
    if kind not in dict(SupportTicket.KINDS) or kind == "verification": kind = "contact"
    form = TicketForm(request.POST or None, request.FILES or None, initial={"subject": request.GET.get("subject", "")})
    if request.method == "POST" and kind in dict(SupportTicket.KINDS) and form.is_valid():
        t = form.save(commit=False); t.user, t.kind = request.user, kind; t.save()
        messages.success(request, "Asante! Our support team received your message and will reply by email or notification.")
        return redirect("m_help")
    kinds = [(k, v) for k, v in SupportTicket.KINDS if k != "verification"]
    return page(request, "members/help.html", {"me": me, "faq": FAQ, "form": form, "kind": kind, "kinds": kinds,
        "show_form": request.method == "POST" or "kind" in request.GET,
        "tickets": SupportTicket.objects.filter(user=request.user)[:5]}, "help", search_hint="Search members, topics, or help articles...")

# ---------- notifications ----------
@login_required
def notifications(request):
    me = me_or_create(request)
    notes = list(request.user.notifications.all()[:60])
    request.user.notifications.filter(read=False).update(read=True)
    return page(request, "members/notifications.html", {"me": me, "notes": notes}, "notifications", header="notify")
