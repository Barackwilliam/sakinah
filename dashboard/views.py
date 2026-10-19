import csv
from datetime import date, timedelta
from functools import wraps
from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mass_mail
from django.db import connection
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from core.models import (Advert, ProfileView, SupportTicket, Article, Broadcast, Event, EventRegistration, Inquiry, Like, Member, Message, MessageTemplate,
                         Notification, Payment, Plan, Report, SiteSetting, Booking)
from .charts import bar_chart, donut, line_chart
from .forms import BroadcastForm, PaymentForm

PALETTE = ["#2f6fe4", "#22a052", "#f0a020", "#8b5cf6", "#e23d5a", "#14a3b8", "#c2410c", "#64748b"]

OWNER_GROUP = "Super Admins"

def is_owner(user):
    """The client's Super Admin (and the developer). Only they manage staff accounts, site settings and the audit log."""
    if not hasattr(user, "_is_owner"):   # asked several times per page; look it up once
        user._is_owner = user.is_superuser or user.groups.filter(name=OWNER_GROUP).exists()
    return user._is_owner

def owner_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return redirect(f"{reverse('login')}?next={reverse('dashboard')}")
        if not is_owner(request.user):
            messages.error(request, "Only the Super Admin can open that page.")
            return redirect("dashboard")
        return view(request, *args, **kwargs)
    return wrapper

def staff_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={reverse('dashboard')}")
        if not request.user.is_staff:
            messages.error(request, "That area is for Sakinah administrators only.")
            return redirect("home")
        return view(request, *args, **kwargs)
    return wrapper

def period(request):
    """Date range from ?from=YYYY-MM-DD&to=YYYY-MM-DD, defaulting to the last 12 months."""
    today = timezone.localdate()
    try: start = date.fromisoformat(request.GET.get("from", ""))
    except ValueError: start = (today.replace(day=1) - timedelta(days=335)).replace(day=1)
    try: end = date.fromisoformat(request.GET.get("to", ""))
    except ValueError: end = today
    return (start, end) if start <= end else (end, start)

def months_between(start, end):
    out, d = [], start.replace(day=1)
    while d <= end and len(out) < 24:
        out.append(d); d = (d + timedelta(days=32)).replace(day=1)
    return out

def per_month(qs, field, months, value=None):
    rows = qs.annotate(m=TruncMonth(field)).values("m").annotate(v=Sum(value) if value else Count("pk"))
    got = {(r["m"].year, r["m"].month): r["v"] or 0 for r in rows if r["m"]}
    return [got.get((m.year, m.month), 0) for m in months]

def change(this, last):
    if not last: return None if not this else 100
    return round((this - last) * 100 / last)

def month_window():
    today = timezone.localdate(); this = today.replace(day=1); last = (this - timedelta(days=1)).replace(day=1)
    return this, last

def group_stats(qs, field, groups, is_datetime=True):
    """{name: (count, % change of new rows this month vs last, new this month, new last month)} for several filters, in one query."""
    this, last = month_window()
    f = f"{field}__date" if is_datetime else field
    agg = {}
    for k, q in groups.items():
        agg[f"{k}__n"] = Count("pk", filter=q); agg[f"{k}__a"] = Count("pk", filter=q & Q(**{f"{f}__gte": this}))
        agg[f"{k}__b"] = Count("pk", filter=q & Q(**{f"{f}__gte": last, f"{f}__lt": this}))
    r = qs.aggregate(**agg)
    return {k: (r[f"{k}__n"], change(r[f"{k}__a"], r[f"{k}__b"]), r[f"{k}__a"], r[f"{k}__b"]) for k in groups}

def message_counts():
    """{(sender member id, recipient member id): number of messages}, from one grouped query."""
    rows = Message.objects.filter(sender__member__isnull=False).values_list("sender__member", "to").annotate(n=Count("pk")).order_by()
    return {(a, b): n for a, b, n in rows}

def badge_counts():
    """Header and sidebar badges. Shown on every admin page, so kept for 30 seconds instead of counted each time."""
    from django.core.cache import cache
    data = cache.get("admin-badges")
    if data is None:
        inquiries, tickets = Inquiry.objects.filter(handled=False).count(), SupportTicket.objects.filter(status="open").count()
        data = {"n_alerts": Report.objects.filter(resolved=False).count() + inquiries + tickets, "n_inbox": inquiries, "n_tickets": tickets,
                "n_msgs": Message.objects.filter(created__date=timezone.localdate()).count(), "n_bookings": Booking.objects.filter(status="new").count()}
        data["n_alerts"] += data["n_bookings"]
        cache.set("admin-badges", data, 30)
    return data

def page(request, template, ctx):
    return render(request, template, {**badge_counts(), "site": SiteSetting.load(), "now_local": timezone.localtime(),
                                      "is_owner": is_owner(request.user), **ctx})

AGE_GROUPS = [("18–25", 18, 25, "#3b82f6"), ("26–35", 26, 35, "#16a34a"), ("36–45", 36, 45, "#e2557a"), ("46–55", 46, 55, "#f5b31b"), ("56+", 56, 200, "#8b5cf6")]

def mutual_pairs():
    """Every mutual match as (member_a, member_b, matched_on), newest first. A match happens when the second like arrives."""
    likes = {}
    for liker, liked, created in Like.objects.filter(user__member__isnull=False).values_list("user__member__id", "member_id", "created"):
        likes[(liker, liked)] = created
    pairs = {}
    for (a, b), t in likes.items():
        back = likes.get((b, a))
        if back and a < b: pairs[(a, b)] = max(t, back)
    members = Member.objects.in_bulk({pk for pair in pairs for pk in pair})
    out = [(members[a], members[b], t) for (a, b), t in pairs.items() if a in members and b in members]
    return sorted(out, key=lambda r: r[2], reverse=True)

def mutual_likes():
    return len(mutual_pairs())

def pair_score(a, b):
    """Simple compatibility estimate shown to admins: shared religion, practice and city, and each other's preferred ages."""
    score = 70 + 8 * (a.religion == b.religion) + 6 * (a.practice == b.practice) + 6 * (a.city == b.city)
    for x, y in ((a, b), (b, a)):
        if x.pref_age_min and x.pref_age_max: score += 5 if x.pref_age_min <= y.age <= x.pref_age_max else -5
    return max(50, min(99, score))

def pair_messages(a, b):
    q = Q(pk__in=[])
    if a.user_id: q |= Q(sender=a.user, to=b)
    if b.user_id: q |= Q(sender=b.user, to=a)
    return Message.objects.filter(q)

def contacted_pairs(pairs):
    """{(a.pk, b.pk)} for the pairs that have exchanged at least one message, found with one query."""
    if not pairs: return set()
    q = Q(pk__in=[])
    for a, b, _ in pairs: q |= Q(sender__member=a, to=b) | Q(sender__member=b, to=a)
    sent = set(Message.objects.filter(q).values_list("sender__member", "to").distinct())
    return {(a.pk, b.pk) for a, b, _ in pairs if (a.pk, b.pk) in sent or (b.pk, a.pk) in sent}

def last_active(m):
    if not m.last_seen: return ("Never", False)
    delta = timezone.now() - m.last_seen
    if delta < timedelta(minutes=5): return ("Online", True)
    if delta < timedelta(hours=1): return (f"{int(delta.total_seconds() // 60)} mins ago", False)
    t = timezone.localtime(m.last_seen); today = timezone.localdate()
    if t.date() == today: return (f"Today {t:%H:%M}", False)
    if t.date() == today - timedelta(days=1): return (f"Yesterday {t:%H:%M}", False)
    return (f"{t:%d %b %Y}", False)

def member_state(m):
    if m.status == "suspended": return ("Suspended", "bad")
    if m.status == "rejected": return ("Rejected", "bad")
    return ("Verified", "ok") if m.verified else ("Pending", "warn")

# ---------- overview ----------
@staff_required
def overview(request):
    today = timezone.localdate(); now = timezone.now()
    span = 6 if request.GET.get("range") == "6" else 12
    end = today; start = (today.replace(day=1) - timedelta(days=31 * (span - 1))).replace(day=1)
    months = months_between(start, end)[-span:]
    this, last = month_window()
    members = Member.objects.all()
    # One query per table for every number on the page (each query is a round trip to the database).
    ages_q = {f"age{i}": Count("pk", filter=Q(age__gte=lo, age__lte=hi)) for i, (_, lo, hi, _) in enumerate(AGE_GROUPS)}
    mc = members.aggregate(total=Count("pk"), new_this=Count("pk", filter=Q(joined__date__gte=this)),
                           new_last=Count("pk", filter=Q(joined__date__gte=last, joined__date__lt=this)),
                           active=Count("pk", filter=Q(last_seen__gte=now - timedelta(days=30))),
                           active_prev=Count("pk", filter=Q(last_seen__gte=now - timedelta(days=60), last_seen__lt=now - timedelta(days=30))),
                           online=Count("pk", filter=Q(last_seen__gte=now - timedelta(minutes=5))),
                           premium=Count("pk", filter=Q(premium_until__gte=today, plan__isnull=False)),
                           males=Count("pk", filter=Q(gender="M")), females=Count("pk", filter=Q(gender="F")), **ages_q)
    total = mc["total"]
    prem_pay = Payment.objects.filter(kind="premium", status="completed")
    pc = Payment.objects.filter(status="completed").aggregate(
        rev_this=Sum("amount", filter=Q(created__date__gte=this)), rev_last=Sum("amount", filter=Q(created__date__gte=last, created__date__lt=this)),
        prem_this=Count("pk", filter=Q(kind="premium", created__date__gte=this)),
        prem_last=Count("pk", filter=Q(kind="premium", created__date__gte=last, created__date__lt=this)))
    rev_this, rev_last = pc["rev_this"] or 0, pc["rev_last"] or 0
    msg = Message.objects.aggregate(total=Count("pk"), today=Count("pk", filter=Q(created__date=today)), this=Count("pk", filter=Q(created__date__gte=this)),
                                    last=Count("pk", filter=Q(created__date__gte=last, created__date__lt=this)))
    ev = Event.objects.aggregate(upcoming=Count("pk", filter=Q(date__gte=today)),
                                 this=Count("pk", filter=Q(date__gte=this, date__lte=today.replace(day=28) + timedelta(days=4))),
                                 last=Count("pk", filter=Q(date__gte=last, date__lt=this)))
    cards = [
        ("Total Members", f"{total:,}", change(mc["new_this"], mc["new_last"]), f"New this month: {mc['new_this']:,}", "m-people", "#0f6b43", ""),
        ("Active Members", f"{mc['active']:,}", change(mc["active"], mc["active_prev"]), f"Online now: {mc['online']:,}", "m-heart", "#a0123c", "online"),
        ("Premium Members", f"{mc['premium']:,}", change(pc["prem_this"], pc["prem_last"]), f"{round(mc['premium'] * 100 / (total or 1), 1)}% of total", "i-crown", "#d4950f", ""),
        ("Total Messages", f"{msg['total']:,}", change(msg["this"], msg["last"]), f"Today: {msg['today']:,}", "m-chat", "#1d63d8", ""),
        ("Upcoming Events", f"{ev['upcoming']:,}", change(ev["this"], ev["last"]), "This month", "m-cal", "#9b1a4d", ""),
        ("Total Revenue", f"{SiteSetting.load().currency} {rev_this:,}", change(rev_this, rev_last), "This month", "i-coins", "#c58a12", ""),
    ]
    reg = per_month(members.filter(joined__date__gte=start), "joined", months)
    prem = per_month(prem_pay.filter(created__date__gte=start), "created", months)
    trend = line_chart([m.strftime("%b") for m in months], [("New Members" if is_owner(request.user) else "All Members", "#16824f", reg),
                                                            ("Premium Members", "#d61f5a", prem)], width=420, height=210, pad_l=34)
    trend["tip"] = {"label": months[-1].strftime("%b %Y"), "new": reg[-1], "prem": prem[-1]}
    males, females = mc["males"], mc["females"]
    mp = round(males * 100 / (total or 1), 1)
    ages = []
    for i, (label, lo, hi, color) in enumerate(AGE_GROUPS):
        n = mc[f"age{i}"]
        ages.append({"label": label, "n": n, "color": color, "pct": round(n * 100 / (total or 1), 1)})
    top = max([a["n"] for a in ages] + [1])
    for a in ages: a["h"] = round(a["n"] * 100 / top)
    latest = list(members.select_related("plan").order_by("-joined")[:5])
    for m in latest: m.state = member_state(m)
    pairs = mutual_pairs()[:5]
    talked = contacted_pairs(pairs)
    matches = [{"a": a, "b": b, "t": t, "contacted": (a.pk, b.pk) in talked} for a, b, t in pairs]
    actives = list(members.filter(last_seen__gte=now - timedelta(days=7)).order_by("-last_seen")[:5])
    for m in actives: m.seen_text, m.online = last_active(m)
    return page(request, "dashboard/overview.html", {
        "nav": "dashboard", "cards": cards, "trend": trend, "span": span, "tinted": not is_owner(request.user),
        "gender": {"m": males, "f": females, "mp": mp, "fp": round(100 - mp, 1) if total else 0, "total": total},
        "ages": ages, "latest": latest, "matches": matches, "actives": actives,
        "payments": recent_payments()})

def recent_payments(n=5):
    rows = list(Payment.objects.select_related("plan", "user__member").order_by("-created")[:n])
    for p in rows:
        m = getattr(p.user, "member", None) if p.user_id else None
        p.who = m.name if m else p.payer_name
        parts = p.who.split(); p.who_short = f"{parts[0]} {parts[1][0]}." if len(parts) > 1 else p.who
    return rows

# ---------- members ----------
MEMBER_FILTERS = {"pending": Q(status="active", verified=False), "verified": Q(status="active", verified=True),
                  "rejected": Q(status="rejected"), "suspended": Q(status="suspended")}
AGE_FILTERS = {"18-25": (18, 25), "26-35": (26, 35), "36-45": (36, 45), "46-55": (46, 55), "56+": (56, 200)}

def filtered_members(g):
    qs = Member.objects.select_related("user", "plan").annotate(n_reports=Count("reports", filter=Q(reports__resolved=False)))
    f = g.get("f", "")
    if f in MEMBER_FILTERS: qs = qs.filter(MEMBER_FILTERS[f])
    elif f == "reported": qs = qs.filter(n_reports__gt=0)
    elif f == "premium": qs = qs.filter(premium_until__gte=timezone.localdate())
    q = g.get("q", "").strip()
    if q: qs = qs.filter(Q(name__icontains=q) | Q(city__icontains=q) | Q(user__email__icontains=q) | Q(user__username__icontains=q) | Q(phone__icontains=q))
    if g.get("gender") in ("M", "F"): qs = qs.filter(gender=g["gender"])
    if g.get("age") in AGE_FILTERS: lo, hi = AGE_FILTERS[g["age"]]; qs = qs.filter(age__gte=lo, age__lte=hi)
    if g.get("city"): qs = qs.filter(city=g["city"])
    plan = g.get("plan", "")
    if plan == "free": qs = qs.exclude(premium_until__gte=timezone.localdate(), plan__isnull=False)
    elif plan.isdigit(): qs = qs.filter(plan_id=int(plan), premium_until__gte=timezone.localdate())
    if g.get("status") in MEMBER_FILTERS: qs = qs.filter(MEMBER_FILTERS[g["status"]])
    if g.get("featured"): qs = qs.filter(featured=True)
    if g.get("photo"): qs = qs.exclude(photo="")
    return qs.order_by("-joined", "-pk")

@staff_required
def members(request):
    from django.core.paginator import Paginator
    from core.forms import LOCATIONS
    g = request.GET
    qs = filtered_members(g)
    per = int(g["per"]) if g.get("per") in ("10", "25", "50", "100") else 10
    pg = Paginator(qs, per).get_page(g.get("page"))
    rows = list(pg.object_list)
    for m in rows: m.state = member_state(m); m.seen_text, m.online = last_active(m)
    st = group_stats(Member.objects.all(), "joined", {"all": Q(pk__isnull=False), **{k: MEMBER_FILTERS[k] for k in ("pending", "verified", "rejected", "suspended")}})
    total = st["all"][0]
    pend, ver, rej, sus = (st[k] for k in ("pending", "verified", "rejected", "suspended"))
    cards = [("Total Members", f"{total:,}", st["all"][1], f"New this month: {st['all'][2]:,}", "m-people", "#0f6b43", "", "up"),
             ("Pending Approval", f"{pend[0]:,}", pend[1], "Awaiting verification", "m-clock", "#e2a83a", "", "am"),
             ("Verified Members", f"{ver[0]:,}", None, f"{round(ver[0] * 100 / (total or 1), 1)}% active and verified", "a-check", "#16a34a", "", "up"),
             ("Rejected Members", f"{rej[0]:,}", rej[1], "Did not meet criteria", "a-user-x", "#d61f5a", "", "dn"),
             ("Suspended Members", f"{sus[0]:,}", sus[1], "Temporarily suspended", "a-pause", "#1d63d8", "", "up")]
    params = g.copy(); params.pop("page", None)
    keep = params.copy(); keep.pop("f", None)
    return page(request, "dashboard/members.html", {"nav": "members", "sub": g.get("f", ""), "pg": pg, "rows": rows, "f": g, "cards": cards,
        "tabs": [("", "All Members", total), ("pending", "Pending", pend[0]), ("verified", "Verified", ver[0]), ("rejected", "Rejected", rej[0]), ("suspended", "Suspended", sus[0])],
        "qs": params.urlencode(), "keep": keep.urlencode(), "per": per, "locations": LOCATIONS, "plans": Plan.objects.filter(price__gt=0), "ages": AGE_FILTERS,
        "page_range": pg.paginator.get_elided_page_range(pg.number, on_each_side=2, on_ends=1), "show_import": "import" in g,
        "search_hint": "Search members by name, email, phone, location...",
        "reports": Report.objects.filter(resolved=False).select_related("member", "reporter")[:6]})

def apply_member_action(m, act, request):
    """One place for single and bulk member actions. Returns a short past-tense label or None."""
    if act == "verify":
        m.verified = True; m.status = "active"; m.save(update_fields=["verified", "status"])
        if m.user_id: Notification.objects.create(user=m.user, title="Your profile is verified", body="Your profile now shows the verified badge.", link=reverse("m_profile"))
        return "verified"
    if act == "unverify": m.verified = False; m.save(update_fields=["verified"]); return "unverified"
    if act == "feature": m.featured = not m.featured; m.save(update_fields=["featured"]); return "featured" if m.featured else "unfeatured"
    if act in ("activate", "suspend", "reject"):
        m.status = {"activate": "active", "suspend": "suspended", "reject": "rejected"}[act]; m.save(update_fields=["status"])
        if m.user_id and act != "activate":
            Notification.objects.create(user=m.user, title=f"Your account was {m.get_status_display().lower()}", body="Contact support if you think this is a mistake.", link=reverse("m_help"))
        return {"activate": "activated", "suspend": "suspended", "reject": "rejected"}[act]
    if act == "resolve": m.reports.update(resolved=True); return "reports resolved"
    if act == "delete":
        if m.user_id and (m.user.is_staff or m.user == request.user): return None   # never delete staff from here
        if m.user_id: m.user.delete()
        else: m.delete()
        return "deleted"
    return None

@staff_required
@require_POST
def member_action(request, pk):
    m = get_object_or_404(Member, pk=pk)
    back = request.POST.get("back") or reverse("dash_members")
    if request.POST.get("act") == "reset_link":
        # for members who cannot receive email: staff copy this link and send it on WhatsApp or SMS
        if not m.user_id or m.user.is_staff:
            messages.error(request, "Password links are only for member accounts.")
        else:
            from django.contrib.admin.models import CHANGE, LogEntry
            from core.views_password import reset_link
            LogEntry.objects.log_actions(request.user.pk, [m], CHANGE, change_message="Created a password reset link", single_object=True)
            SupportTicket.objects.filter(user=m.user, subject__startswith="Password reset help", status="open").update(status="closed")
            messages.success(request, f"Password reset link for {m.name} (works once, for 3 days). Copy it and send it to them: {reset_link(request, m.user)}")
        return redirect(back if back.startswith("/") else reverse("dash_members"))
    name, done = m.name, apply_member_action(m, request.POST.get("act"), request)
    if done: messages.success(request, f"{name} {done}.")
    else: messages.error(request, "That action is not allowed for this member.")
    return redirect(back if back.startswith("/") else reverse("dash_members"))

@staff_required
@require_POST
def members_bulk(request):
    ids = [int(i) for i in request.POST.getlist("ids") if i.isdigit()]
    act = request.POST.get("act")
    back = request.POST.get("back") or reverse("dash_members")
    back = back if back.startswith("/") else reverse("dash_members")
    if act == "export":
        return members_csv(request, ids=ids)
    if not ids:
        messages.error(request, "Select at least one member first."); return redirect(back)
    chosen = Member.objects.filter(pk__in=ids).select_related("user")
    if act == "message":
        title, body = request.POST.get("subject", "").strip(), request.POST.get("body", "").strip()
        if not title:
            messages.error(request, "Write a subject for the message."); return redirect(back)
        sent = [Notification(user=m.user, title=title[:120], body=body.replace("{name}", m.first_name)) for m in chosen if m.user_id]
        Notification.objects.bulk_create(sent)
        skipped = len(ids) - len(sent)
        messages.success(request, f"Message sent to {len(sent)} member{'s' if len(sent) != 1 else ''}." + (f" {skipped} without a login account were skipped." if skipped else ""))
        return redirect(back)
    done = [apply_member_action(m, act, request) for m in chosen]
    n = sum(1 for d in done if d)
    if n: messages.success(request, f"{n} member{'s' if n != 1 else ''} {next(d for d in done if d)}.")
    if n < len(done): messages.error(request, f"{len(done) - n} member{'s' if len(done) - n != 1 else ''} skipped (staff accounts cannot be changed here).")
    return redirect(back)

@staff_required
def members_csv(request, ids=None):
    qs = Member.objects.filter(pk__in=ids).select_related("user", "plan") if ids else filtered_members(request.GET)
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="sakinah-members-{timezone.localdate()}.csv"'
    w = csv.writer(resp)
    w.writerow(["Member ID", "Name", "Email", "Phone", "Gender", "Age", "City", "Occupation", "Plan", "Premium until", "Verified", "Status", "Joined", "Last active"])
    for m in qs:
        w.writerow([m.code, m.name, m.user.email if m.user_id else "", m.phone, m.get_gender_display(), m.age, m.city, m.occupation,
                    m.plan.name if m.is_premium else "Free", m.premium_until or "", "yes" if m.verified else "no", m.get_status_display(),
                    f"{m.joined:%Y-%m-%d}", f"{m.last_seen:%Y-%m-%d %H:%M}" if m.last_seen else ""])
    return resp

@staff_required
@require_POST
def members_import(request):
    """CSV with a header row: name, age, gender (M/F), city, occupation; optional phone, education, bio."""
    f = request.FILES.get("file")
    if not f or not f.name.lower().endswith(".csv"):
        messages.error(request, "Choose a .csv file to import."); return redirect(reverse("dash_members") + "?import=1#import")
    try: rows = list(csv.DictReader(f.read().decode("utf-8-sig").splitlines()))
    except UnicodeDecodeError:
        messages.error(request, "The file must be saved as UTF-8 CSV."); return redirect(reverse("dash_members") + "?import=1#import")
    created, errors = 0, []
    for n, r in enumerate(rows, start=2):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
        gender = {"m": "M", "male": "M", "f": "F", "female": "F"}.get(r.get("gender", "").lower())
        age = r.get("age", "")
        if not r.get("name") or not gender or not age.isdigit() or not 18 <= int(age) <= 99 or not r.get("city"):
            errors.append(n); continue
        Member.objects.create(name=r["name"][:80], age=int(age), gender=gender, city=r["city"][:60], occupation=r.get("occupation", "")[:80],
                              phone=r.get("phone", "")[:20], education=r.get("education", "")[:80], bio=r.get("bio", "")[:600])
        created += 1
    if created: messages.success(request, f"Imported {created} member{'s' if created != 1 else ''}.")
    if errors: messages.error(request, f"Skipped {len(errors)} row{'s' if len(errors) != 1 else ''} with missing or invalid name, age, gender or city (rows {', '.join(map(str, errors[:10]))}{'...' if len(errors) > 10 else ''}).")
    return redirect("dash_members")

# ---------- match and activities ----------
@staff_required
def matches(request):
    from django.core.paginator import Paginator
    from core.forms import LOCATIONS
    g, today, now = request.GET, timezone.localdate(), timezone.now()
    tab = g.get("tab", "")
    this, last = month_window()
    pairs = mutual_pairs()
    members = Member.objects.all()
    if tab == "messages":
        msgs = Message.objects.select_related("sender__member", "to").order_by("-created")
        pair = None
        if g.get("a", "").isdigit() and g.get("b", "").isdigit():
            a, b = Member.objects.filter(pk=g["a"]).first(), Member.objects.filter(pk=g["b"]).first()
            if a and b: msgs, pair = pair_messages(a, b).select_related("sender__member", "to").order_by("-created"), (a, b)
        if g.get("q"): msgs = msgs.filter(Q(body__icontains=g["q"]) | Q(to__name__icontains=g["q"]) | Q(sender__member__name__icontains=g["q"]))
        pg = Paginator(msgs, 25).get_page(g.get("page"))
        from urllib.parse import urlencode
        base = "?" + urlencode({"tab": "messages", **({"a": g["a"], "b": g["b"]} if pair else {"q": g.get("q", "")})})
        return page(request, "dashboard/matches_messages.html", {"nav": "matches", "sub": "messages", "pg": pg, "pair": pair, "f": g, "base": base})
    if tab == "all":
        sent = message_counts()
        rows = [{"a": a, "b": b, "t": t, "score": pair_score(a, b), "n": sent.get((a.pk, b.pk), 0) + sent.get((b.pk, a.pk), 0)} for a, b, t in pairs]
        pg = Paginator(rows, 20).get_page(g.get("page"))
        return page(request, "dashboard/matches_all.html", {"nav": "matches", "sub": "all", "pg": pg, "total": len(rows)})
    month = lambda qs: group_stats(qs, "created", {"n": Q(pk__isnull=False)})["n"]   # (total, change, this month)
    likes, views, regs, msgs = month(Like.objects), month(ProfileView.objects), month(EventRegistration.objects), month(Message.objects)
    acts_this = likes[2] + views[2] + regs[2]
    acts_last = likes[3] + views[3] + regs[3]
    new_matches = sum(1 for *_, t in pairs if timezone.localtime(t).date() >= this)
    old_matches = sum(1 for *_, t in pairs if last <= timezone.localtime(t).date() < this)
    ms = group_stats(members, "joined", {"n": Q(pk__isnull=False)})["n"]
    cards = [("Total Members", f"{ms[0]:,}", ms[1], f"New this month: {ms[2]:,}", "m-people", "#a0123c"),
             ("Total Matches", f"{len(pairs):,}", change(new_matches, old_matches), "New matches this month", "m-heart", "#e11d63"),
             ("Messages Exchanged", f"{msgs[2]:,}", msgs[1], "This month", "m-chat", "#a0123c"),
             ("Upcoming Events", f"{Event.objects.filter(date__gte=today).count():,}", None, "Scheduled", "m-cal", "#a0123c"),
             ("Total Activities", f"{acts_this:,}", change(acts_this, acts_last), "This month", "m-people", "#16824f")]
    # find potential matches
    sq = members.filter(status="active")
    gender = g.get("gender", "F")
    if gender in ("M", "F"): sq = sq.filter(gender=gender)
    age = g.get("age", "")
    if age in AGE_FILTERS: lo, hi = AGE_FILTERS[age]; sq = sq.filter(age__gte=lo, age__lte=hi)
    if g.get("city"): sq = sq.filter(city=g["city"])
    if g.get("type") == "verified": sq = sq.filter(verified=True)
    elif g.get("type") == "premium": sq = sq.filter(premium_until__gte=today, plan__isnull=False)
    suggestions = list(sq.exclude(photo="").order_by("-compatibility", "-verified", "-joined")[:12])
    recent = [{"a": a, "b": b, "t": t, "score": pair_score(a, b)} for a, b, t in pairs[:5]]
    # activity feed
    feed = []
    for lk in Like.objects.select_related("user__member", "member").order_by("-created")[:8]:
        m = getattr(lk.user, "member", None)
        if m: feed.append((lk.created, m, "liked a profile", "Like", "m-heart", "#d61f45"))
    for r in EventRegistration.objects.select_related("user__member", "event").order_by("-created")[:6]:
        m = getattr(r.user, "member", None)
        if m: feed.append((r.created, m, f"joined an event: {r.event.title}", "Event Registration", "m-cal", "#16824f"))
    for msg in Message.objects.select_related("sender__member").order_by("-created")[:6]:
        m = getattr(msg.sender, "member", None)
        if m: feed.append((msg.created, m, "sent a message", "Message", "m-chat", "#7c3aed"))
    for a, b, t in pairs[:4]:
        feed.append((t, b, "received a new match", "New Match", "m-heart", "#d61f45"))
    for m in members.order_by("-joined")[:4]:
        feed.append((m.joined, m, "joined Sakinah", "New Member", "m-user", "#1d63d8"))
    feed = sorted(feed, key=lambda r: r[0], reverse=True)[:6]
    events = list(Event.objects.filter(date__gte=today).annotate(reg_count=Count("registrations")).order_by("date")[:4])
    # match statistics
    start = (today.replace(day=1) - timedelta(days=31 * 11)).replace(day=1); months = months_between(start, today)[-12:]
    match_months = [sum(1 for *_, t in pairs if (timezone.localtime(t).year, timezone.localtime(t).month) == (mo.year, mo.month)) for mo in months]
    chart = bar_chart([mo.strftime("%b") for mo in months], [
        ("New Members", "#16824f", per_month(members.filter(joined__date__gte=start), "joined", months)),
        ("Matches", "#e2557a", match_months),
        ("Messages", "#3b82f6", per_month(Message.objects.filter(created__date__gte=start), "created", months)),
        ("Event Participants", "#f5b31b", per_month(EventRegistration.objects.filter(created__date__gte=start), "created", months))], width=460, height=170)
    return page(request, "dashboard/matches.html", {"nav": "matches", "sub": "", "cards": cards, "f": g, "gender": gender, "suggestions": suggestions,
        "recent": recent, "feed": feed, "events": events, "chart": chart, "locations": LOCATIONS, "ages": AGE_FILTERS,
        "search_hint": "Search members by name, email, location..."})

@staff_required
def report_csv(request):
    start, end = period(request)
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="sakinah-report-{start}-{end}.csv"'
    w = csv.writer(resp)
    paid = Payment.objects.filter(status="completed", created__date__range=(start, end))
    w.writerow(["Sakinah report", f"{start} to {end}"]); w.writerow([])
    for label, value in [("New members", Member.objects.filter(joined__date__range=(start, end)).count()),
                         ("Total members", Member.objects.count()), ("New adverts", Advert.objects.filter(created__date__range=(start, end)).count()),
                         ("Events", Event.objects.filter(date__range=(start, end)).count()),
                         ("Event registrations", EventRegistration.objects.filter(created__date__range=(start, end)).count()),
                         ("Payments", paid.count()), ("Revenue", paid.aggregate(s=Sum("amount"))["s"] or 0)]:
        w.writerow([label, value])
    return resp


# ---------- communications ----------
def recipients(filters):
    qs = Member.objects.filter(user__isnull=False, user__is_active=True)
    g = filters.get("gender")
    if g in ("M", "F"): qs = qs.filter(gender=g)
    if filters.get("verified") == "yes": qs = qs.filter(verified=True)
    elif filters.get("verified") == "no": qs = qs.filter(verified=False)
    if filters.get("age_min"): qs = qs.filter(age__gte=int(filters["age_min"]))
    if filters.get("age_max"): qs = qs.filter(age__lte=int(filters["age_max"]))
    if filters.get("city"): qs = qs.filter(city=filters["city"])
    plan = filters.get("plan")
    if plan == "premium": qs = qs.filter(premium_until__gte=timezone.localdate())
    elif plan == "free": qs = qs.exclude(premium_until__gte=timezone.localdate())
    elif plan: qs = qs.filter(plan__name=plan, premium_until__gte=timezone.localdate())
    return qs.select_related("user")

def raw_filters(data):
    out = {k: data.get(k, "") for k in ("gender", "verified", "city", "plan")}
    for k in ("age_min", "age_max"):
        if data.get(k, "").isdigit(): out[k] = data[k]
    return {k: v for k, v in out.items() if v}

def deliver(b, sender):
    people = list(recipients(b.filters))
    if b.channel == "notification":
        Notification.objects.bulk_create([Notification(user=m.user, title=b.subject, body=b.body.replace("{name}", m.name)) for m in people])
    elif b.channel == "inapp":
        Message.objects.bulk_create([Message(sender=sender, to=m, body=f"{b.subject}\n\n{b.body.replace('{name}', m.name)}") for m in people])
    else:
        send_mass_mail([(b.subject, b.body.replace("{name}", m.name), None, [m.user.email]) for m in people if m.user.email], fail_silently=False)
    b.recipients, b.status, b.sent_at = len(people), "sent", timezone.now()
    b.save()
    return len(people)

@staff_required
def communications(request):
    tpl = MessageTemplate.objects.filter(pk=request.GET.get("template") or 0).first()
    form = BroadcastForm(request.POST or None, initial={"channel": request.GET.get("channel", "email"),
        **({"subject": tpl.subject, "body": tpl.body} if tpl else {})})
    if request.method == "POST" and "preview" not in request.POST and form.is_valid():
        b = form.save(commit=False); b.created_by = request.user; b.filters = form.filters()
        if request.POST.get("draft"):
            b.save(); messages.success(request, "Saved as draft.")
        else:
            try: n = deliver(b, request.user); messages.success(request, f"Sent to {n} member{'s' if n != 1 else ''}.")
            except Exception as e: b.save(); messages.error(request, f"Could not send: {e}. Saved as draft.")
        return redirect("dash_comms")
    start = timezone.localdate() - timedelta(days=27)
    days = [start + timedelta(days=7 * i) for i in range(4)]
    this, last = month_window()
    chans = ("email", "inapp", "notification")
    rsum = lambda q: Sum("recipients", filter=q)
    agg = {"m_a": rsum(Q(sent_at__date__gte=this)), "m_b": rsum(Q(sent_at__date__gte=last, sent_at__date__lt=this))}
    for c in chans:
        agg[f"{c}_a"] = rsum(Q(channel=c, sent_at__date__gte=this)); agg[f"{c}_b"] = rsum(Q(channel=c, sent_at__date__gte=last, sent_at__date__lt=this))
        for i, d in enumerate(days): agg[f"{c}_w{i}"] = rsum(Q(channel=c, sent_at__date__gte=d, sent_at__date__lt=d + timedelta(days=7)))
    r = {k: v or 0 for k, v in Broadcast.objects.filter(status="sent").aggregate(**agg).items()}   # every chart and card number in one query
    weekly = lambda c: [r[f"{c}_w{i}"] for i in range(len(days))]
    monthly = lambda c="m": (r[f"{c}_a"], change(r[f"{c}_a"], r[f"{c}_b"]))
    member_msgs = Message.objects.filter(created__date__gte=this).count()
    cards = [("Total Messages", *monthly(), "mail", "#e23d5a"), ("Emails Sent", *monthly("email"), "send", "#2f6fe4"),
             ("In-App Messages", *monthly("inapp"), "chat", "#22a052"), ("Notifications", *monthly("notification"), "bell", "#e0a21a"),
             ("Member Messages", member_msgs, None, "people", "#8b5cf6")]
    rc = recipients({}).aggregate(n_all=Count("pk"), n_verified=Count("pk", filter=Q(verified=True)),
                                  n_premium=Count("pk", filter=Q(premium_until__gte=timezone.localdate())),
                                  n_women=Count("pk", filter=Q(gender="F")), n_men=Count("pk", filter=Q(gender="M")))
    groups = [("All Members", rc["n_all"]), ("Verified Members", rc["n_verified"]), ("Premium Members", rc["n_premium"]), ("Women", rc["n_women"]), ("Men", rc["n_men"])]
    groups += [(c["city"], c["n"]) for c in Member.objects.filter(user__isnull=False).values("city").annotate(n=Count("pk")).order_by("-n")[:4]]
    return page(request, "dashboard/communications.html", {"nav": "comms", "form": form, "cards": cards,
        "templates": MessageTemplate.objects.all(), "history": Broadcast.objects.select_related("created_by")[:8],
        "estimate": recipients(raw_filters(request.POST if request.method == "POST" else request.GET)).count(),
        "chart": bar_chart([d.strftime("%d %b") for d in days], [("Emails", "#e23d5a", weekly("email")), ("In-App", "#2f6fe4", weekly("inapp")),
                                                                 ("Notifications", "#22a052", weekly("notification"))]),
        "groups": groups, "email_live": "console" not in settings.EMAIL_BACKEND, "channels": Broadcast.CHANNELS})

# ---------- payments ----------
@staff_required
def payments(request):
    start, end = period(request)
    form = PaymentForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            p = form.save(commit=False); p.recorded_by = request.user; p.save()
            activated = p.activate()
            if activated: Notification.objects.create(user=p.user, title=f"{p.plan.name} plan activated", body=f"Thank you! Your {p.plan.name} plan is active until {p.user.member.premium_until:%d %b %Y}.", link=reverse("premium"))
            messages.success(request, f"Payment {p.invoice_no} recorded." + (f" {p.plan.name} activated for {p.payer_name}." if activated else ""))
            return redirect("dash_payments")
        messages.error(request, "Please correct the payment form.")
    all_paid = Payment.objects.filter(status="completed")
    paid = all_paid.filter(created__date__range=(start, end))
    months = months_between(start, end)
    this, last = month_window()
    amt = lambda q: Sum("amount", filter=q)
    in_period, m_a, m_b = Q(created__date__range=(start, end)), Q(created__date__gte=this), Q(created__date__gte=last, created__date__lt=this)
    agg = {"total": amt(in_period), "count": Count("pk", filter=in_period), "a": amt(m_a), "b": amt(m_b),
           "n_a": Count("pk", filter=m_a), "n_b": Count("pk", filter=m_b)}
    for k, _ in Payment.KINDS:
        agg[f"k_{k}"] = amt(in_period & Q(kind=k)); agg[f"{k}_a"] = amt(m_a & Q(kind=k)); agg[f"{k}_b"] = amt(m_b & Q(kind=k))
    r = {k: v or 0 for k, v in all_paid.aggregate(**agg).items()}   # every card and the type split in one query
    total, by_kind = r["total"], {k: r[f"k_{k}"] for k, _ in Payment.KINDS}
    cur = SiteSetting.load().currency
    cards = [("Total Revenue", f"{cur} {total:,}", change(r["a"], r["b"]), "coins", "#e23d5a"),
             ("Total Transactions", f"{r['count']:,}", change(r["n_a"], r["n_b"]), "cart", "#2f6fe4"),
             ("Paying Members", f"{paid.exclude(user=None).values('user').distinct().count():,}", None, "people", "#22a052"),
             ("Premium Revenue", f"{cur} {by_kind['premium']:,}", change(r["premium_a"], r["premium_b"]), "crown", "#e0a21a"),
             ("Advert Revenue", f"{cur} {by_kind['advert']:,}", change(r["advert_a"], r["advert_b"]), "doc", "#8b5cf6")]
    colors = {"membership": "#e23d5a", "premium": "#2f6fe4", "advert": "#22a052", "event": "#f0a020", "other": "#8b5cf6"}
    by_month = {}
    for row in paid.annotate(m=TruncMonth("created")).values("kind", "m").annotate(v=Sum("amount")).order_by():
        if row["m"]: by_month[(row["kind"], row["m"].year, row["m"].month)] = row["v"] or 0
    trend = line_chart([m.strftime("%b") for m in months],
        [(label, colors[k], [by_month.get((k, m.year, m.month), 0) / 1000 for m in months]) for k, label in Payment.KINDS])
    kinds = donut([(label, colors[k], by_kind[k]) for k, label in Payment.KINDS if by_kind[k]] or [("No payments", "#eceef3", 0)])
    gw = dict(Payment.GATEWAYS)
    gateways = list(paid.values("gateway").annotate(s=Sum("amount"), n=Count("pk")).order_by("-s"))
    for g in gateways: g["name"], g["pct"] = gw.get(g["gateway"], g["gateway"]), round(g["s"] * 100 / (total or 1))
    today = timezone.localdate()
    rev = dict(paid.values_list("plan").annotate(s=Sum("amount")).order_by())
    subs = dict(Member.objects.filter(premium_until__gte=today).values_list("plan").annotate(n=Count("pk")).order_by())
    n_free = None
    plans = []
    for p in Plan.objects.all():
        if not p.price and n_free is None: n_free = Member.objects.exclude(premium_until__gte=today).count()
        s = rev.get(p.pk) or 0
        plans.append({"name": p.name, "subs": subs.get(p.pk, 0) if p.price else n_free, "revenue": s, "pct": round(s * 100 / (by_kind["premium"] or 1))})
    other = Payment.objects.aggregate(pending=Sum("amount", filter=Q(status="pending")), refunds=Sum("amount", filter=Q(status="refunded", created__date__range=(start, end))))
    pending, refunds = other["pending"] or 0, other["refunds"] or 0
    return page(request, "dashboard/payments.html", {"nav": "payments", "start": start, "end": end, "cards": cards, "trend": trend,
        "kinds": kinds, "total": total, "gateways": gateways, "plans": plans,
        "plan_totals": (sum(p["subs"] for p in plans), sum(p["revenue"] for p in plans)),
        "recent": Payment.objects.select_related("plan")[:6], "form": form, "show_form": request.method == "POST" or "new" in request.GET,
        "summary": [("Collected in period", total, "ok"), ("Pending payments", pending, "warn"), ("Refunds", refunds, "bad"), ("Net revenue", total - refunds, "ok")]})

@staff_required
@require_POST
def payment_action(request, pk):
    p = get_object_or_404(Payment, pk=pk)
    act = request.POST.get("act")
    if act == "complete" and p.status == "pending":
        p.status = "completed"; p.save(update_fields=["status"]); p.activate()
    elif act == "refund" and p.status == "completed":
        p.status = "refunded"; p.save(update_fields=["status"])
    messages.success(request, f"{p.invoice_no} is now {p.get_status_display().lower()}.")
    return redirect("dash_payments")

@staff_required
def payments_csv(request):
    start, end = period(request)
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="sakinah-payments-{start}-{end}.csv"'
    w = csv.writer(resp)
    w.writerow(["Invoice", "Date", "Payer", "Phone", "Type", "Plan", "Months", "Description", "Gateway", "Reference", "Amount", "Status"])
    for p in Payment.objects.filter(created__date__range=(start, end)).select_related("plan").order_by("created"):
        w.writerow([p.invoice_no, p.created.strftime("%Y-%m-%d %H:%M"), p.payer_name, p.payer_phone, p.get_kind_display(),
                    p.plan.name if p.plan else "", p.months, p.description, p.get_gateway_display(), p.reference, p.amount, p.get_status_display()])
    return resp

@staff_required
def receipt(request, pk):
    return render(request, "dashboard/receipt.html", {"p": get_object_or_404(Payment.objects.select_related("plan"), pk=pk), "site": SiteSetting.load()})

# ---------- search ----------
@staff_required
def search(request):
    q = request.GET.get("q", "").strip()
    res = {}
    if q:
        res = {"Members": [(m.name, f"{m.age} · {m.city}", reverse("member", args=[m.pk])) for m in Member.objects.filter(Q(name__icontains=q) | Q(user__email__icontains=q))[:10]],
               "Adverts": [(a.title, a.city, reverse("advert", args=[a.slug])) for a in Advert.objects.filter(title__icontains=q)[:10]],
               "Events": [(e.title, f"{e.date:%d %b %Y}", reverse("events") + f"#e{e.pk}") for e in Event.objects.filter(title__icontains=q)[:10]],
               "Articles": [(a.title, f"{a.published:%d %b %Y}", a.get_absolute_url()) for a in Article.objects.filter(title__icontains=q)[:10]],
               "Payments": [(p.invoice_no, f"{p.payer_name} · {p.amount:,}", reverse("dash_receipt", args=[p.pk])) for p in Payment.objects.filter(Q(invoice_no__icontains=q) | Q(payer_name__icontains=q) | Q(reference__icontains=q))[:10]]}
    return page(request, "dashboard/search.html", {"nav": "", "q": q, "res": res})
