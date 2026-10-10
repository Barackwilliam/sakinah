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
from core.models import (Advert, SupportTicket, Article, Broadcast, Event, EventRegistration, Inquiry, Like, Member, Message, MessageTemplate,
                         Notification, Payment, Plan, Report, SiteSetting)
from .charts import bar_chart, donut, line_chart
from .forms import BroadcastForm, PaymentForm

PALETTE = ["#2f6fe4", "#22a052", "#f0a020", "#8b5cf6", "#e23d5a", "#14a3b8", "#c2410c", "#64748b"]

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

def stat(qs, field, is_datetime=True):
    """Percent change of new rows this month against last month."""
    this, last = month_window()
    f = f"{field}__date" if is_datetime else field
    return change(qs.filter(**{f"{f}__gte": this}).count(), qs.filter(**{f"{f}__gte": last, f"{f}__lt": this}).count())

def badge_counts():
    return {"n_alerts": Report.objects.filter(resolved=False).count() + Inquiry.objects.filter(handled=False).count()
                        + SupportTicket.objects.filter(status="open").count(),
            "n_inbox": Inquiry.objects.filter(handled=False).count()}

def page(request, template, ctx):
    return render(request, template, {**badge_counts(), "site": SiteSetting.load(), **ctx})

# ---------- overview ----------
@staff_required
def overview(request):
    start, end = period(request)
    months = months_between(start, end); labels = [m.strftime("%b") for m in months]
    today = timezone.localdate()
    paid = Payment.objects.filter(status="completed")
    revenue_total = paid.filter(created__date__range=(start, end)).aggregate(s=Sum("amount"))["s"] or 0
    this, last = month_window()
    rev_this = paid.filter(created__date__gte=this).aggregate(s=Sum("amount"))["s"] or 0
    rev_last = paid.filter(created__date__gte=last, created__date__lt=this).aggregate(s=Sum("amount"))["s"] or 0
    mutual = mutual_likes()
    cards = [
        ("Total Members", Member.objects.count(), stat(Member.objects, "joined"), "This month", "people", "#e23d5a"),
        ("Active Matches", mutual, None, "Mutual likes", "heart-f", "#2f6fe4"),
        ("Active Adverts", Advert.objects.filter(active=True).count(), stat(Advert.objects, "created"), "This month", "doc", "#22a052"),
        ("Upcoming Events", Event.objects.filter(date__gte=today, date__lte=today + timedelta(days=92)).count(), None, "Next 3 months", "cal-f", "#e0a21a"),
        ("Published Articles", Article.objects.count(), stat(Article.objects, "published", is_datetime=False), "This month", "book", "#8b5cf6"),
        ("Total Revenue", f"{SiteSetting.load().currency} {revenue_total:,}", change(rev_this, rev_last), "Selected period", "chart", "#ec4f84"),
    ]
    growth = line_chart(labels, [
        ("Members", "#e23d5a", per_month(Member.objects.filter(joined__date__range=(start, end)), "joined", months)),
        ("Adverts", "#2f6fe4", per_month(Advert.objects.filter(created__date__range=(start, end)), "created", months)),
        ("Events", "#22a052", per_month(Event.objects.filter(date__range=(start, end)), "date", months)),
        ("Payments", "#f0a020", per_month(paid.filter(created__date__range=(start, end)), "created", months)),
    ])
    plans = [("Free", "#e23d5a", Member.objects.filter(Q(plan=None) | Q(premium_until__lt=today) | Q(premium_until=None)).count())]
    for i, p in enumerate(Plan.objects.filter(price__gt=0)):
        plans.append((p.name, PALETTE[i % len(PALETTE)], Member.objects.filter(plan=p, premium_until__gte=today).count()))
    total_m = Member.objects.count() or 1
    cities = list(Member.objects.values("city").annotate(n=Count("pk")).order_by("-n")[:10])
    for c in cities: c["pct"] = round(c["n"] * 100 / total_m)
    gateways = list(paid.filter(created__date__range=(start, end)).values("gateway").annotate(n=Count("pk"), s=Sum("amount")).order_by("-s"))
    gw_names = dict(Payment.GATEWAYS)
    for g in gateways: g["name"] = gw_names.get(g["gateway"], g["gateway"])
    return page(request, "dashboard/overview.html", {
        "nav": "dashboard", "start": start, "end": end, "cards": cards, "growth": growth,
        "plans": donut(plans), "total_members": Member.objects.count(), "cities": cities,
        "recent_members": Member.objects.order_by("-joined")[:5],
        "events": Event.objects.filter(date__gte=today).annotate(n=Count("registrations")).order_by("date")[:5],
        "adverts": Advert.objects.select_related("category").order_by("-created")[:5],
        "gateways": gateways, "gw_total": (sum(g["n"] for g in gateways), sum(g["s"] for g in gateways)),
        "system": system_status()})

def mutual_likes():
    """Pairs of members who liked each other."""
    pairs = set()
    for user_id, member_user in Like.objects.filter(member__user__isnull=False).values_list("user_id", "member__user_id"):
        pairs.add((user_id, member_user))
    return sum(1 for a, b in pairs if (b, a) in pairs) // 2

def system_status():
    try:
        with connection.cursor() as c: c.execute("SELECT 1")
        db = True
    except Exception: db = False
    storage = "Supabase Storage" if getattr(settings, "AWS_STORAGE_BUCKET_NAME", None) else "Local disk"
    email = settings.EMAIL_BACKEND.rsplit(".", 2)[-2]
    since = timezone.now() - timedelta(days=1)
    return [("Website Status", "Online", True), ("Database", "Healthy" if db else "Unreachable", db),
            ("Database engine", connection.vendor.title(), True), ("Media storage", storage, True),
            ("Email Service", "SMTP" if email == "smtp" else "Console (not sending)", email == "smtp"),
            ("Active Users (24h)", Member.objects.filter(last_seen__gte=since).count(), True),
            ("Open reports", Report.objects.filter(resolved=False).count(), not Report.objects.filter(resolved=False).exists())]

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

# ---------- members ----------
@staff_required
def members(request):
    q, f = request.GET.get("q", ""), request.GET.get("f", "")
    qs = Member.objects.select_related("user", "plan").annotate(n_reports=Count("reports", filter=Q(reports__resolved=False))).order_by("-joined")
    if q: qs = qs.filter(Q(name__icontains=q) | Q(city__icontains=q) | Q(user__email__icontains=q) | Q(user__username__icontains=q))
    if f == "pending": qs = qs.filter(verified=False)
    elif f == "verified": qs = qs.filter(verified=True)
    elif f == "reported": qs = qs.filter(n_reports__gt=0)
    elif f == "premium": qs = qs.filter(premium_until__gte=timezone.localdate())
    return page(request, "dashboard/members.html", {"nav": "members", "rows": qs[:200], "q": q, "f": f,
        "counts": {"all": Member.objects.count(), "pending": Member.objects.filter(verified=False).count(),
                   "reported": Member.objects.filter(reports__resolved=False).distinct().count()},
        "reports": Report.objects.filter(resolved=False).select_related("member", "reporter")[:10]})

@staff_required
@require_POST
def member_action(request, pk):
    m = get_object_or_404(Member, pk=pk)
    act = request.POST.get("act")
    if act == "verify": m.verified = not m.verified; m.save(update_fields=["verified"])
    elif act == "feature": m.featured = not m.featured; m.save(update_fields=["featured"])
    elif act == "resolve": m.reports.update(resolved=True)
    if act == "verify" and m.verified and m.user_id:
        Notification.objects.create(user=m.user, title="Your profile is verified", body="Your profile now shows the Imethibitishwa badge.",
                                    link=reverse("member", args=[m.pk]))
    messages.success(request, f"{m.name} updated.")
    return redirect(request.POST.get("back") or reverse("dash_members"))

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
    sent = Broadcast.objects.filter(status="sent")
    def weekly(channel):
        return [sent.filter(channel=channel, sent_at__date__gte=d, sent_at__date__lt=d + timedelta(days=7)).aggregate(s=Sum("recipients"))["s"] or 0 for d in days]
    this, last = month_window()
    def monthly(channel=None):
        q = sent if channel is None else sent.filter(channel=channel)
        a = q.filter(sent_at__date__gte=this).aggregate(s=Sum("recipients"))["s"] or 0
        b = q.filter(sent_at__date__gte=last, sent_at__date__lt=this).aggregate(s=Sum("recipients"))["s"] or 0
        return a, change(a, b)
    member_msgs = Message.objects.filter(created__date__gte=this).count()
    cards = [("Total Messages", *monthly(), "mail", "#e23d5a"), ("Emails Sent", *monthly("email"), "send", "#2f6fe4"),
             ("In-App Messages", *monthly("inapp"), "chat", "#22a052"), ("Notifications", *monthly("notification"), "bell", "#e0a21a"),
             ("Member Messages", member_msgs, None, "people", "#8b5cf6")]
    groups = [("All Members", recipients({}).count()), ("Verified Members", recipients({"verified": "yes"}).count()),
              ("Premium Members", recipients({"plan": "premium"}).count()), ("Women", recipients({"gender": "F"}).count()),
              ("Men", recipients({"gender": "M"}).count())]
    groups += [(c["city"], c["n"]) for c in Member.objects.filter(user__isnull=False).values("city").annotate(n=Count("pk")).order_by("-n")[:4]]
    return page(request, "dashboard/communications.html", {"nav": "comms", "form": form, "cards": cards,
        "templates": MessageTemplate.objects.all(), "history": Broadcast.objects.select_related("created_by")[:8],
        "estimate": recipients(raw_filters(request.POST if request.method == "POST" else request.GET)).count(),
        "chart": bar_chart([d.strftime("%d %b") for d in days], [("Emails", "#e23d5a", weekly("email")), ("In-App", "#2f6fe4", weekly("inapp")),
                                                                 ("Notifications", "#22a052", weekly("notification"))]),
        "groups": groups, "email_live": "smtp" in settings.EMAIL_BACKEND, "channels": Broadcast.CHANNELS})

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
    total = paid.aggregate(s=Sum("amount"))["s"] or 0
    by_kind = {k: paid.filter(kind=k).aggregate(s=Sum("amount"))["s"] or 0 for k, _ in Payment.KINDS}
    this, last = month_window()
    def mchange(qs, value=True):
        a = qs.filter(created__date__gte=this); b = qs.filter(created__date__gte=last, created__date__lt=this)
        return change(a.aggregate(s=Sum("amount"))["s"] or 0, b.aggregate(s=Sum("amount"))["s"] or 0) if value else change(a.count(), b.count())
    cur = SiteSetting.load().currency
    cards = [("Total Revenue", f"{cur} {total:,}", mchange(all_paid), "coins", "#e23d5a"),
             ("Total Transactions", f"{paid.count():,}", mchange(all_paid, False), "cart", "#2f6fe4"),
             ("Paying Members", f"{paid.exclude(user=None).values('user').distinct().count():,}", None, "people", "#22a052"),
             ("Premium Revenue", f"{cur} {by_kind['premium']:,}", mchange(all_paid.filter(kind='premium')), "crown", "#e0a21a"),
             ("Advert Revenue", f"{cur} {by_kind['advert']:,}", mchange(all_paid.filter(kind='advert')), "doc", "#8b5cf6")]
    colors = {"membership": "#e23d5a", "premium": "#2f6fe4", "advert": "#22a052", "event": "#f0a020", "other": "#8b5cf6"}
    trend = line_chart([m.strftime("%b") for m in months],
        [(label, colors[k], [v / 1000 for v in per_month(paid.filter(kind=k), "created", months, "amount")]) for k, label in Payment.KINDS])
    kinds = donut([(label, colors[k], by_kind[k]) for k, label in Payment.KINDS if by_kind[k]] or [("No payments", "#eceef3", 0)])
    gw = dict(Payment.GATEWAYS)
    gateways = list(paid.values("gateway").annotate(s=Sum("amount"), n=Count("pk")).order_by("-s"))
    for g in gateways: g["name"], g["pct"] = gw.get(g["gateway"], g["gateway"]), round(g["s"] * 100 / (total or 1))
    plans = []
    for p in Plan.objects.all():
        s = paid.filter(plan=p).aggregate(s=Sum("amount"))["s"] or 0
        plans.append({"name": p.name, "subs": Member.objects.filter(plan=p, premium_until__gte=timezone.localdate()).count() if p.price else
                      Member.objects.exclude(premium_until__gte=timezone.localdate()).count(), "revenue": s, "pct": round(s * 100 / (by_kind["premium"] or 1))})
    pending = Payment.objects.filter(status="pending").aggregate(s=Sum("amount"))["s"] or 0
    refunds = Payment.objects.filter(status="refunded", created__date__range=(start, end)).aggregate(s=Sum("amount"))["s"] or 0
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
