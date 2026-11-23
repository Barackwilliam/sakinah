"""Everything the client manages from the dashboard, described once: list columns, filters, form fields and row actions.
The generic views in views_manage.py turn each Resource into list / add / edit / delete pages, so the client never needs
the developer-only Django admin."""
from django.utils.translation import gettext_lazy as _l
from datetime import date
from django import forms
from django.contrib.admin.models import LogEntry
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from core.forms import LOCATIONS
from .forms import PaymentForm
from core.models import (AdOrder, AdPackage, Advert, BannerOrder, BannerSlot, Article, ArticleCategory, Booking, Broadcast, Destination, Event, Package, PackagePhoto, PackageReview, EventCategory, EventRegistration, FeatureStrip, Inquiry,
                         Member, MessageTemplate, Notification, Payment, Plan, PremiumPerk, Report, ServiceCategory, SupportTicket, Vendor)

# ---------- small column helpers ----------
def thumb(field):
    def f(o):
        img = getattr(o, field)
        return format_html('<span class="th2"><img src="{}" alt=""></span>', img.url) if img else mark_safe('<span class="th2"></span>')
    return f

def pill(text, tone):
    return format_html('<span class="pill {}">{}</span>', tone, text)

def yesno(field, yes=_l("Yes"), no=_l("No"), tone_yes="ok", tone_no="mut"):
    return lambda o: pill(yes, tone_yes) if getattr(o, field) else pill(no, tone_no)

def money(field):
    return lambda o: f"TSh {getattr(o, field) or 0:,}"

def when(field, fmt="%d %b %Y"):
    def f(o):
        v = getattr(o, field)
        if not v: return "—"
        if hasattr(v, "tzinfo") and v.tzinfo: v = timezone.localtime(v)
        return v.strftime(fmt)
    return f

def bold(field, sub=None):
    return lambda o: format_html('<b class="mn">{}</b>{}', getattr(o, field), format_html('<small class="mc">{}</small>', sub(o)) if sub else "")

def user_label(u):
    if u is None: return "—"
    m = getattr(u, "member", None)
    return m.name if m else (u.get_full_name() or u.get_username())

# ---------- forms ----------
class ImageWidget(forms.ClearableFileInput):
    """Shows the current picture as a thumbnail with Change / Remove instead of Django's plain "Currently / Clear" text."""
    template_name = "dashboard/widgets/image.html"
    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        url = getattr(value, "name", "") or ""
        ctx["widget"]["is_image"] = url.lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "gif", "webp", "svg")
        return ctx

def pretty_files(form_cls):
    for f in form_cls.base_fields.values():
        if isinstance(f, forms.FileField):
            f.widget = ImageWidget(attrs={"accept": "image/*"} if isinstance(f, forms.ImageField) else {})
    return form_cls

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
TIME = forms.TimeInput(attrs={"type": "time"}, format="%H:%M")
AREA = lambda rows=4: forms.Textarea(attrs={"rows": rows})

class SlugMixin:
    """Fill the slug from the title/name when the admin leaves it empty, and keep it unique."""
    slug_from = "name"
    def clean_slug(self):
        raw = self.cleaned_data.get("slug") or slugify(self.data.get(self.add_prefix(self.slug_from), ""))[:60] or "item"
        slug, n, model = raw, 2, self._meta.model
        while model.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            slug = f"{raw[:55]}-{n}"; n += 1
        return slug

def model_form(model, fields, widgets=None, slug_from=None, help=None, labels=None):
    attrs = {"Meta": type("Meta", (), {"model": model, "fields": fields, "widgets": widgets or {}, "help_texts": help or {}, "labels": labels or {}})}
    if "slug" in fields:
        attrs["slug_from"] = slug_from or "name"
        form = type(f"{model.__name__}Form", (SlugMixin, forms.ModelForm), attrs)
        form.base_fields["slug"].required = False
        form.base_fields["slug"].help_text = _l("Leave empty to create it from the ") + attrs["slug_from"] + "."
        return pretty_files(form)
    return pretty_files(type(f"{model.__name__}Form", (forms.ModelForm,), attrs))

class MemberAdminForm(forms.ModelForm):
    city = forms.ChoiceField(choices=[(c, c) for c in LOCATIONS])
    class Meta:
        model = Member
        fields = ["name", "age", "gender", "city", "occupation", "education", "marital_status", "religion", "practice", "phone", "headline",
                  "bio", "interests", "photo", "verified", "featured", "status", "plan", "premium_until", "compatibility"]
        widgets = {"bio": AREA(4), "premium_until": DATE}
        help_texts = {"premium_until": _l("The plan is active until this date. Leave empty for a free member."),
                      "compatibility": _l("Match score (0-100) shown on suggestions."), "status": _l("Rejected and suspended members are hidden from everyone.")}
pretty_files(MemberAdminForm)

# ---------- resource definition ----------
class Resource:
    title = ""; icon = "m-doc"; nav = ""; model = None; form = None
    columns = []; search = []; filters = []; ordering = ["-pk"]
    can_add = can_edit = can_delete = True; owner_only = False; per_page = 20
    actions = {}          # name -> (label, tone, fn(obj, request) -> message)
    front = {}            # name -> fn(obj) -> True to also show that action as a button on the row
    row_link = None       # fn(obj) -> url for the first column
    note = ""
    def queryset(self): return self.model.objects.all()
    def filtered(self, g):
        qs = self.queryset()
        q = g.get("q", "").strip()
        if q and self.search:
            cond = Q()
            for f in self.search: cond |= Q(**{f + "__icontains": q})
            qs = qs.filter(cond)
        for key, label, choices, apply in self.filters:
            v = g.get(key, "")
            if v and v in dict(choices()): qs = apply(qs, v)
        return qs.order_by(*self.ordering)
    def label(self, obj): return str(obj)
    def after_save(self, obj, request, created): pass

REGISTRY = {}
def register(key):
    def deco(cls):
        r = cls(); r.key = key; REGISTRY[key] = r; return cls
    return deco

def toggle(field, on_msg, off_msg):
    def fn(obj, request):
        setattr(obj, field, not getattr(obj, field)); obj.save(update_fields=[field])
        return on_msg if getattr(obj, field) else off_msg
    return fn

def set_field(field, value, msg):
    def fn(obj, request):
        setattr(obj, field, value); obj.save(update_fields=[field]); return msg
    return fn

# ---------- events ----------
@register("events")
class Events(Resource):
    title, icon, nav, model = _l("Events"), "m-cal", "events", Event
    form = model_form(Event, ["title", "category", "date", "start_time", "end_time", "city", "capacity", "attendees", "tags", "description", "image"],
                      widgets={"date": DATE, "start_time": TIME, "end_time": TIME, "description": AREA(3)},
                      help={"attendees": _l("People already going before online registration (walk-ins)."), "capacity": _l("Leave empty for no limit.")})
    search = ["title", "city", "tags"]
    filters = [("when", _l("All dates"), lambda: [("upcoming", _l("Upcoming")), ("past", _l("Past"))],
                lambda qs, v: qs.filter(date__gte=date.today()) if v == "upcoming" else qs.filter(date__lt=date.today())),
               ("category", _l("All categories"), lambda: [(str(c.pk), c.name) for c in EventCategory.objects.all()], lambda qs, v: qs.filter(category_id=v))]
    ordering = ["-date"]
    def queryset(self): return Event.objects.select_related("category").annotate(reg_count=Count("registrations"))
    columns = [("", thumb("image")), (_l("Event"), bold("title", lambda o: o.category.name if o.category else "")), (_l("Date"), when("date")),
               (_l("Time"), lambda o: f"{o.start_time:%H:%M}" if o.start_time else "—"), (_l("Location"), lambda o: o.city),
               (_l("Registrations"), lambda o: format_html('<a class="va" href="{}?event={}">{}</a>', reverse("dash_manage", args=["registrations"]), o.pk, o.reg_count)),
               (_l("Seats"), lambda o: _l("Open") if o.capacity is None else f"{o.seats_left} of {o.capacity} left")]

@register("event-categories")
class EventCategories(Resource):
    title, icon, nav, model = _l("Event Categories"), "m-cal", "events", EventCategory
    form = model_form(EventCategory, ["name", "slug", "order"])
    search, ordering = ["name"], ["order", "pk"]
    columns = [(_l("Name"), bold("name")), (_l("Slug"), lambda o: o.slug), (_l("Events"), lambda o: o.events.count()), (_l("Order"), lambda o: o.order)]

@register("registrations")
class Registrations(Resource):
    title, icon, nav, model = _l("Event Registrations"), "m-ticket", "events", EventRegistration
    can_add = can_edit = False
    search = ["event__title", "user__username", "user__email", "user__member__name"]
    filters = [("event", _l("All events"), lambda: [(str(e.pk), f"{e.title} ({e.date:%d %b})") for e in Event.objects.order_by("-date")], lambda qs, v: qs.filter(event_id=v))]
    ordering = ["-created"]
    def queryset(self): return EventRegistration.objects.select_related("event", "user__member")
    columns = [(_l("Member"), lambda o: format_html('<b class="mn">{}</b><small class="mc">{}</small>', user_label(o.user), o.user.email)),
               (_l("Phone"), lambda o: getattr(getattr(o.user, "member", None), "phone", "") or "—"),
               (_l("Event"), lambda o: o.event.title), (_l("Event date"), lambda o: o.event.date.strftime("%d %b %Y")), (_l("Registered"), when("created", "%d %b %Y %H:%M"))]

# ---------- membership plans ----------
@register("plans")
class Plans(Resource):
    title, icon, nav, model = _l("Membership Plans"), "m-crown", "plans", Plan
    form = model_form(Plan, ["name", "price", "period", "order", "tagline", "daily_messages", "call_minutes", "features", "popular", "icon"],
                      widgets={"features": AREA(8)},
                      help={"features": _l("One feature per line. Start a line with - for a feature the plan does NOT include. Write 'All Silver features' to include the previous plan."),
                            "daily_messages": _l("Messages this plan may send in 24 hours. 0 = none, -1 = unlimited."),
                            "call_minutes": _l("Voice and video call minutes for each month of the plan. 0 = none, -1 = unlimited.")})
    search, ordering = ["name"], ["order", "pk"]
    columns = [("", thumb("icon")), (_l("Plan"), bold("name", lambda o: o.tagline)), (_l("Price"), lambda o: f"TSh {o.price:,} {o.period}"),
               (_l("Allowance"), lambda o: f"{_l('Unlimited') if o.daily_messages < 0 else o.daily_messages} messages a day · "
                                     f"{_l('Unlimited') if o.call_minutes < 0 else str(o.call_minutes) + ' min'} calls"),
               (_l("Active members"), lambda o: o.members.filter(premium_until__gte=date.today()).count() if o.price else "—"),
               (_l("Most popular"), yesno("popular", _l("Yes"), "—"))]

@register("perks")
class Perks(Resource):
    title, icon, nav, model = _l("Premium Perks"), "m-star", "plans", PremiumPerk
    form = model_form(PremiumPerk, ["text", "order"])
    search, ordering = ["text"], ["order", "pk"]
    columns = [(_l("Perk"), lambda o: o.text), (_l("Order"), lambda o: o.order)]

# ---------- content ----------
@register("articles")
class Articles(Resource):
    title, icon, nav, model = _l("Articles"), "m-book", "content", Article
    form = model_form(Article, ["title", "slug", "category", "author", "published", "featured", "image", "excerpt", "body", "tags"],
                      widgets={"published": DATE, "excerpt": AREA(2), "body": AREA(14)}, slug_from="title",
                      help={"body": _l("Separate paragraphs with an empty line. Start a line with ## for a heading.")})
    search = ["title", "author", "tags"]
    filters = [("category", _l("All categories"), lambda: [(str(c.pk), c.name) for c in ArticleCategory.objects.all()], lambda qs, v: qs.filter(category_id=v))]
    def queryset(self): return Article.objects.select_related("category")
    ordering = ["-published", "-pk"]
    columns = [("", thumb("image")), (_l("Article"), bold("title", lambda o: o.category.name if o.category else "")), (_l("Author"), lambda o: o.author or "—"),
               (_l("Published"), when("published")), (_l("Views"), lambda o: f"{o.views:,}"), (_l("Featured"), yesno("featured", _l("Featured"), "—", "info"))]
    actions = {"feature": (_l("Feature / unfeature"), "", toggle("featured", "featured", "unfeatured"))}

@register("article-categories")
class ArticleCategories(Resource):
    title, icon, nav, model = _l("Article Categories"), "m-book", "content", ArticleCategory
    form = model_form(ArticleCategory, ["name", "slug", "icon", "order"])
    search, ordering = ["name"], ["order", "pk"]
    columns = [(_l("Name"), bold("name")), (_l("Articles"), lambda o: o.articles.count()), (_l("Order"), lambda o: o.order)]

@register("home-strips")
class HomeStrips(Resource):
    title, icon, nav, model = _l("Home Page Highlights"), "m-home", "content", FeatureStrip
    form = model_form(FeatureStrip, ["title", "text", "icon", "order"])
    ordering = ["order", "pk"]
    note = _l("The short feature boxes shown on the home page.")
    columns = [(_l("Title"), bold("title")), (_l("Text"), lambda o: o.text), (_l("Order"), lambda o: o.order)]

# ---------- communication ----------
@register("templates")
class Templates(Resource):
    title, icon, nav, model = _l("Message Templates"), "m-doc", "comms", MessageTemplate
    form = model_form(MessageTemplate, ["name", "description", "subject", "body", "icon", "color", "order"], widgets={"body": AREA(8)},
                      help={"body": _l("Use {name} for the member's name.")})
    search, ordering = ["name", "subject"], ["order", "pk"]
    columns = [(_l("Template"), bold("name", lambda o: o.description)), (_l("Subject"), lambda o: o.subject),
               ("", lambda o: format_html('<a class="va" href="{}?template={}">Use</a>', reverse("dash_comms"), o.pk))]

@register("broadcasts")
class Broadcasts(Resource):
    title, icon, nav, model = _l("Message History"), "m-send", "comms", Broadcast
    can_add = can_edit = False
    search = ["subject", "body"]
    filters = [("channel", _l("All channels"), lambda: list(Broadcast.CHANNELS), lambda qs, v: qs.filter(channel=v)),
               ("status", _l("All statuses"), lambda: [("sent", _l("Sent")), ("draft", _l("Draft"))], lambda qs, v: qs.filter(status=v))]
    ordering = ["-created"]
    columns = [(_l("Subject"), bold("subject", lambda o: o.get_channel_display())), (_l("Recipients"), lambda o: f"{o.recipients:,}"),
               (_l("Status"), lambda o: pill(o.get_status_display(), "ok" if o.status == "sent" else "warn")),
               (_l("Created"), when("created", "%d %b %Y %H:%M")), (_l("By"), lambda o: user_label(o.created_by))]

# ---------- support ----------
@register("tickets")
class Tickets(Resource):
    title, icon, nav, model = _l("Support Tickets"), "m-headset", "support", SupportTicket
    can_add = False
    form = model_form(SupportTicket, ["reply", "status"], widgets={"reply": AREA(6)},
                      help={"reply": _l("The member gets this answer as a notification in their dashboard.")})
    search = ["subject", "message", "user__username", "user__email"]
    filters = [("status", _l("All statuses"), lambda: list(SupportTicket.STATUS), lambda qs, v: qs.filter(status=v)),
               ("kind", _l("All types"), lambda: list(SupportTicket.KINDS), lambda qs, v: qs.filter(kind=v))]
    ordering = ["status", "-created"]
    def queryset(self): return SupportTicket.objects.select_related("user__member")
    columns = [(_l("Subject"), lambda o: format_html('<b class="mn">{}</b><small class="mc">{}</small>', o.subject, o.message[:90])),
               (_l("Type"), lambda o: o.get_kind_display()), (_l("From"), lambda o: user_label(o.user)),
               (_l("Attachment"), lambda o: format_html('<a class="va" href="{}" target="_blank">Open file</a>', o.attachment.url) if o.attachment else "—"),
               (_l("Received"), when("created", "%d %b %Y %H:%M")),
               (_l("Status"), lambda o: pill(_l("Answered") if o.reply and o.status == "closed" else o.get_status_display(), "warn" if o.status == "open" else "ok"))]
    actions = {"close": (_l("Close / reopen"), "", lambda o, r: (set_field("status", "closed" if o.status == "open" else "open", "updated")(o, r)))}
    def after_save(self, obj, request, created):
        if obj.reply and obj.user_id and not obj.replied_at:
            obj.replied_at = timezone.now(); obj.status = "closed"; obj.save(update_fields=["replied_at", "status"])
            Notification.objects.create(user=obj.user, title=f"Support replied: {obj.subject}"[:120], body=obj.reply, link=reverse("m_help"))
        if obj.kind == "verification" and obj.status == "closed" and request.POST.get("verify_member") and obj.user_id and hasattr(obj.user, "member"):
            obj.user.member.verified = True; obj.user.member.save(update_fields=["verified"])

@register("reports")
class Reports(Resource):
    title, icon, nav, model = _l("Member Reports"), "m-flag", "support", Report
    can_add = can_edit = False
    search = ["member__name", "details", "reporter__username"]
    filters = [("resolved", _l("Open and resolved"), lambda: [("0", _l("Open")), ("1", _l("Resolved"))], lambda qs, v: qs.filter(resolved=v == "1"))]
    ordering = ["resolved", "-created"]
    def queryset(self): return Report.objects.select_related("member", "reporter")
    columns = [(_l("Reported member"), lambda o: format_html('<a href="{}" target="_blank"><b class="mn">{}</b></a><small class="mc">{}</small>', reverse("member", args=[o.member_id]), o.member.name, o.member.city)),
               (_l("Reason"), lambda o: o.get_reason_display()), (_l("Details"), lambda o: (o.details or "—")[:120]), (_l("By"), lambda o: user_label(o.reporter)),
               (_l("Date"), when("created")), (_l("Status"), lambda o: pill(_l("Resolved"), "ok") if o.resolved else pill(_l("Open"), "bad"))]
    actions = {"resolve": (_l("Mark resolved / open"), "", toggle("resolved", "marked resolved", "reopened")),
               "suspend": (_l("Suspend this member"), "dang", lambda o, r: (set_field("status", "suspended", "suspended")(o.member, r)))}

@register("inquiries")
class Inquiries(Resource):
    title, icon, nav, model = _l("Vendor Inquiries"), "m-mail", "support", Inquiry
    can_add = can_edit = False
    search = ["name", "phone", "message", "advert__title"]
    filters = [("handled", _l("All"), lambda: [("0", _l("New")), ("1", _l("Handled"))], lambda qs, v: qs.filter(handled=v == "1"))]
    ordering = ["handled", "-created"]
    def queryset(self): return Inquiry.objects.select_related("advert")
    columns = [(_l("Customer"), lambda o: format_html('<b class="mn">{}</b><small class="mc">{}</small>', o.name, o.phone)), (_l("Service"), lambda o: o.advert.title),
               (_l("Type"), lambda o: o.get_kind_display()), (_l("Event date"), when("event_date")),
               (_l("Message"), lambda o: (o.message or "—")[:100]), (_l("Received"), when("created")), (_l("Status"), lambda o: pill(_l("Handled"), "ok") if o.handled else pill(_l("New"), "warn"))]
    actions = {"handled": (_l("Mark handled / new"), "", toggle("handled", "marked handled", "marked new"))}

# ---------- marketing ----------
@register("adverts")
class Adverts(Resource):
    title, icon, nav, model = _l("Adverts"), "i-mega", "marketing", Advert
    form = model_form(Advert, ["title", "slug", "category", "vendor", "city", "price", "price_unit", "negotiable", "image", "description", "highlights",
                               "includes", "extras", "availability", "details", "map_query", "featured", "active", "expires", "package"],
                      widgets={"expires": DATE, "description": AREA(5), "highlights": AREA(3), "includes": AREA(3), "extras": AREA(3), "details": AREA(3)}, slug_from="title")
    search = ["title", "city", "vendor__name"]
    filters = [("category", _l("All categories"), lambda: [(str(c.pk), c.name) for c in ServiceCategory.objects.all()], lambda qs, v: qs.filter(category_id=v)),
               ("active", _l("All"), lambda: [("1", _l("Active")), ("0", _l("Hidden"))], lambda qs, v: qs.filter(active=v == "1"))]
    ordering = ["-created"]
    def queryset(self): return Advert.objects.select_related("vendor", "category")
    row_link = lambda self, o: reverse("advert", args=[o.slug])
    columns = [("", thumb("image")), (_l("Advert"), bold("title", lambda o: o.vendor.name)), (_l("Category"), lambda o: o.category.name), (_l("Location"), lambda o: o.city),
               (_l("Price"), lambda o: f"TSh {o.price:,}" if o.price else "—"), (_l("Views"), lambda o: f"{o.views:,}"),
               (_l("Status"), lambda o: format_html("{} {}", pill(_l("Active"), "ok") if o.active else pill(_l("Hidden"), "mut"), pill(_l("Featured"), "info") if o.featured else ""))]
    actions = {"active": (_l("Show / hide"), "", toggle("active", "is now visible", "is now hidden")), "feature": (_l("Feature / unfeature"), "", toggle("featured", "featured", "unfeatured"))}

# ---------- Advertise with us ----------
def approve_ad(o, r):
    """Confirm the vendor's payment and publish (or extend) the advert."""
    p = o.payment
    if p is None: return "has no payment yet, so it was not published"
    if p.status in ("failed", "refunded"): return "has a failed or refunded payment, so it was not published"
    fresh = p.status == "pending"
    if fresh: p.status = "completed"; p.recorded_by = r.user; p.save(update_fields=["status", "recorded_by"])
    if o.status == "live" and not fresh: return "is already live"
    ad = o.publish(r)
    return f"is live until {ad.expires:%d %b %Y}"

def reject_ad(o, r):
    p = o.payment
    if p and p.status == "pending": p.status = "failed"; p.save(update_fields=["status"])
    if o.advert_id and o.status == "live":
        o.advert.active = False; o.advert.save(update_fields=["active"])
    o.status = "rejected"; o.save(update_fields=["status"])
    if o.user_id:
        Notification.objects.create(user=o.user, link=o.get_absolute_url(), title=f"Your advert was not approved: {o.title}"[:120], body=o.admin_note)
    return "was not approved"

AD_TONES = {"awaiting_payment": "warn", "paid": "info", "live": "ok", "rejected": "bad"}

@register("ad-orders")
class AdOrders(Resource):
    title, icon, nav, model = _l("Advert Requests"), "i-mega", "marketing", AdOrder
    form = model_form(AdOrder, ["package", "business_name", "contact_name", "phone", "email", "category", "city", "title", "description",
                                "price", "price_unit", "negotiable", "image", "photo2", "photo3", "photo4", "admin_note"],
                      widgets={"description": AREA(5), "admin_note": AREA(3)})
    can_add = False
    note = _l("Vendors who used Advertise with us. Confirm the payment to publish the advert; it then runs for the package's days.")
    search = ["business_name", "title", "phone", "email"]
    filters = [("status", _l("All statuses"), lambda: AdOrder.STATUS, lambda qs, v: qs.filter(status=v))]
    def queryset(self): return AdOrder.objects.select_related("package", "category", "advert").prefetch_related("payments")
    row_link = lambda self, o: o.get_absolute_url()
    columns = [("", thumb("image")), (_l("Advert"), bold("title", lambda o: f"{o.business_name} · {o.phone}")), (_l("Package"), lambda o: o.package.name),
               (_l("Amount"), lambda o: f"TSh {o.package.price:,}"),
               (_l("Payment"), lambda o: pill(o.payment.get_status_display(), {"pending": "warn", "completed": "ok"}.get(o.payment.status, "bad")) if o.payment else pill(_l("Not paid"), "mut")),
               (_l("Status"), lambda o: pill(_l("Expired"), "bad") if o.is_expired else pill(o.get_status_display(), AD_TONES.get(o.status, "mut"))),
               (_l("Runs until"), lambda o: o.expires.strftime("%d %b %Y") if o.expires else "—")]
    actions = {"approve": (_l("Confirm payment & publish"), "", approve_ad), "reject": (_l("Do not approve"), "dang", reject_ad)}
    front = {"approve": lambda o: o.payment_pending}

@register("ad-packages")
class AdPackages(Resource):
    title, icon, nav, model = _l("Advert Packages"), "i-tag", "marketing", AdPackage
    form = model_form(AdPackage, ["name", "slug", "tagline", "price", "days", "max_photos", "features", "featured", "home_page", "popular", "active", "order"],
                      widgets={"features": AREA(6)})
    note = _l("The packages vendors choose on the Advertise with us page.")
    search, ordering = ["name"], ["order", "price"]
    columns = [(_l("Package"), bold("name", lambda o: o.tagline)), (_l("Price"), money("price")), (_l("Days"), lambda o: o.days),
               (_l("Photos"), lambda o: o.max_photos), (_l("Requests"), lambda o: o.orders.count()),
               (_l("Status"), lambda o: format_html("{} {} {}", pill(_l("Active"), "ok") if o.active else pill(_l("Hidden"), "mut"),
                                                    pill(_l("Featured"), "info") if o.featured else "", pill(_l("Home page"), "info") if o.home_page else ""))]
    actions = {"active": (_l("Show / hide"), "", toggle("active", "is now visible", "is now hidden"))}

# ---------- banners ----------
def approve_banner(o, r):
    """Confirm the payment if it is still pending, then publish the banner for the place's days."""
    p = o.payment
    if p is None: return "has no payment yet, so it was not published"
    if p.status in ("failed", "refunded"): return "has a failed or refunded payment, so it was not published"
    if p.status == "pending": p.status = "completed"; p.recorded_by = r.user; p.save(update_fields=["status", "recorded_by"])
    if o.is_live: return "is already live"
    if o.slot.free <= 0 and o.status != "review": return "was not published: the place is fully booked"
    end = o.go_live(r)
    return f"is live until {end:%d %b %Y}"

def reject_banner(o, r):
    p = o.payment
    if p and p.status == "pending": p.status = "failed"; p.save(update_fields=["status"])
    o.status = "rejected"; o.save(update_fields=["status"])
    if o.user_id:
        Notification.objects.create(user=o.user, link=o.get_absolute_url(), title=f"Your banner was not approved: {o.business_name}"[:120], body=o.admin_note)
    return "was not approved"

def pause_banner(o, r):
    if o.status == "paused": o.status = "live"; o.save(update_fields=["status"]); return "is showing again"
    if o.status != "live": return "is not live"
    o.status = "paused"; o.save(update_fields=["status"]); return "is paused"

BANNER_TONES = {"awaiting_payment": "warn", "review": "info", "live": "ok", "paused": "mut", "rejected": "bad"}

@register("banners")
class Banners(Resource):
    title, icon, nav, model = _l("Banners"), "i-image", "marketing", BannerOrder
    form = model_form(BannerOrder, ["slot", "business_name", "title", "link", "image", "starts", "expires", "admin_note"],
                      widgets={"starts": DATE, "expires": DATE, "admin_note": AREA(3)})
    can_add = False
    note = _l("Banners booked by advertisers. Check the picture, then approve it to publish; it runs for the place's days.")
    search = ["business_name", "title", "link"]
    filters = [("status", _l("All statuses"), lambda: BannerOrder.STATUS, lambda qs, v: qs.filter(status=v)),
               ("slot", _l("All places"), lambda: [(str(s.pk), s.name) for s in BannerSlot.objects.all()], lambda qs, v: qs.filter(slot_id=v))]
    def queryset(self): return BannerOrder.objects.select_related("slot").prefetch_related("payments")
    row_link = lambda self, o: o.get_absolute_url()
    columns = [("", thumb("image")), (_l("Banner"), bold("business_name", lambda o: o.title)), (_l("Place"), lambda o: o.slot.name),
               (_l("Amount"), lambda o: f"TSh {o.slot.price:,}"),
               (_l("Payment"), lambda o: pill(o.payment.get_status_display(), {"pending": "warn", "completed": "ok"}.get(o.payment.status, "bad")) if o.payment else pill(_l("Not paid"), "mut")),
               (_l("Status"), lambda o: pill(_l("Expired"), "bad") if o.is_expired else pill(o.get_status_display(), BANNER_TONES.get(o.status, "mut"))),
               (_l("Views / clicks"), lambda o: f"{o.views:,} / {o.clicks:,}"),
               (_l("Runs until"), lambda o: o.expires.strftime("%d %b %Y") if o.expires else "—")]
    actions = {"approve": (_l("Approve & publish"), "", approve_banner), "pause": (_l("Pause / show again"), "", pause_banner),
               "reject": (_l("Do not approve"), "dang", reject_banner)}
    front = {"approve": lambda o: o.status == "review" or (o.payment_pending and not o.is_live)}

@register("banner-slots")
class BannerSlots(Resource):
    title, icon, nav, model = _l("Banner Places"), "i-tag", "marketing", BannerSlot
    form = model_form(BannerSlot, ["name", "description", "price", "days", "max_live", "active", "order"], widgets={"description": AREA(2)})
    can_add = can_delete = False
    note = _l("The three places where banners appear, with their price, days and how many banners take turns there.")
    ordering = ["order", "pk"]
    columns = [(_l("Place"), bold("name", lambda o: o.get_place_display())), (_l("Price"), money("price")), (_l("Days"), lambda o: o.days),
               (_l("Size"), lambda o: o.size_text), (_l("Booked"), lambda o: f"{o.taken()} / {o.max_live}"),
               (_l("Status"), lambda o: pill(_l("Active"), "ok") if o.active else pill(_l("Hidden"), "mut"))]
    actions = {"active": (_l("Show / hide"), "", toggle("active", "is now bookable", "is now hidden"))}

@register("vendors")
class Vendors(Resource):
    title, icon, nav, model = _l("Vendors"), "m-briefcase", "marketing", Vendor
    form = model_form(Vendor, ["name", "slug", "city", "phone", "logo", "verified", "member_since", "why_choose"], widgets={"member_since": DATE, "why_choose": AREA(3)})
    search, ordering = ["name", "city"], ["name"]
    columns = [("", thumb("logo")), (_l("Vendor"), bold("name", lambda o: o.phone)), (_l("City"), lambda o: o.city), (_l("Adverts"), lambda o: o.adverts.count()),
               (_l("Verified"), yesno("verified", _l("Verified"), "—"))]

@register("service-categories")
class ServiceCategories(Resource):
    title, icon, nav, model = _l("Service Categories"), "m-grid", "marketing", ServiceCategory
    form = model_form(ServiceCategory, ["name", "slug", "blurb", "button_label", "image", "order"], widgets={"blurb": AREA(2)})
    search, ordering = ["name"], ["order", "pk"]
    columns = [("", thumb("image")), (_l("Category"), bold("name", lambda o: o.blurb[:60])), (_l("Adverts"), lambda o: Advert.objects.filter(category=o).count()), (_l("Order"), lambda o: o.order)]

# ---------- honeymoon ----------
def booking_status(status, msg):
    def fn(o, r):
        o.status = status; o.save(update_fields=["status"])
        if o.user_id and status in ("confirmed", "cancelled"):
            Notification.objects.create(user=o.user, link=o.package.get_absolute_url(),
                title=f"Honeymoon booking {'confirmed' if status == 'confirmed' else 'cancelled'}: {o.package.title}",
                body=_l("Hongera! Your honeymoon booking is confirmed. Our team will share the travel details with you.") if status == "confirmed"
                     else _l("Your honeymoon booking request was cancelled. Contact us if you would like to choose other dates."))
        return msg
    return fn

BOOKING_TONES = {"new": "warn", "contacted": "info", "confirmed": "ok", "cancelled": "bad"}

@register("bookings")
class Bookings(Resource):
    title, icon, nav, model = _l("Honeymoon Bookings"), "m-cal", "honeymoon", Booking
    can_add = False
    form = model_form(Booking, ["status", "travel_date", "couples", "name", "phone", "email", "message"], widgets={"travel_date": DATE, "message": AREA(3)})
    search = ["name", "phone", "email", "package__title"]
    filters = [("status", _l("All statuses"), lambda: Booking.STATUS, lambda qs, v: qs.filter(status=v)),
               ("package__destination", _l("All destinations"), lambda: [(str(d.pk), d.name) for d in Destination.objects.all()], lambda qs, v: qs.filter(package__destination_id=v))]
    ordering = ["-created"]
    def queryset(self): return Booking.objects.select_related("package__destination", "user")
    columns = [(_l("Couple"), lambda o: format_html('<b class="mn">{}</b><small class="mc">{}{}</small>', o.name, o.phone, f" · {o.email}" if o.email else "")),
               (_l("Package"), lambda o: format_html('<a class="va" href="{}" target="_blank">{}</a><small class="mc">{}</small>', o.package.get_absolute_url(), o.package.title, o.package.destination.name)),
               (_l("Travel date"), when("travel_date")), (_l("Couples"), lambda o: o.couples), (_l("Estimated total"), lambda o: f"TSh {o.total:,}"),
               (_l("Received"), when("created", "%d %b %Y %H:%M")), (_l("Status"), lambda o: pill(o.get_status_display(), BOOKING_TONES[o.status]))]
    actions = {"contacted": (_l("Mark contacted"), "", booking_status("contacted", "marked contacted")),
               "confirmed": (_l("Confirm booking"), "", booking_status("confirmed", "confirmed and the member notified")),
               "cancelled": (_l("Cancel booking"), "dang", booking_status("cancelled", "cancelled"))}

@register("packages")
class Packages(Resource):
    title, icon, nav, model = _l("Honeymoon Packages"), "i-gem", "honeymoon", Package
    form = model_form(Package, ["title", "slug", "destination", "location", "package_type", "badge", "badge_tone", "image", "price", "days", "nights", "stars",
                                "stay", "meals", "meals_detail", "extra", "extra_icon", "flights", "transfer", "romance", "overview", "highlights", "itinerary",
                                "inclusions", "exclusions", "accommodation", "activities", "important_info", "ideal_for", "rating", "reviews",
                                "discount", "free_addons", "all_inclusive", "featured", "active", "order"],
                      widgets={k: AREA(4) for k in ("overview", "highlights", "itinerary", "inclusions", "exclusions", "accommodation", "activities", "important_info", "ideal_for")},
                      slug_from="title")
    search = ["title", "location", "destination__name"]
    filters = [("destination", _l("All destinations"), lambda: [(str(d.pk), d.name) for d in Destination.objects.all()], lambda qs, v: qs.filter(destination_id=v)),
               ("active", _l("All"), lambda: [("1", _l("Active")), ("0", _l("Hidden"))], lambda qs, v: qs.filter(active=v == "1"))]
    ordering = ["destination__order", "order", "pk"]
    def queryset(self): return Package.objects.select_related("destination").annotate(n_book=Count("bookings", distinct=True), n_photos=Count("photos", distinct=True))
    row_link = lambda self, o: o.get_absolute_url()
    columns = [("", thumb("image")), (_l("Package"), bold("title", lambda o: f"{o.destination.name} · {o.days} days {o.nights} nights")), (_l("Price"), money("price")),
               (_l("Badge"), lambda o: o.badge or "—"),
               (_l("Photos"), lambda o: format_html('<a class="va" href="{}?package={}">{}</a>', reverse("dash_manage", args=["package-photos"]), o.pk, o.n_photos)),
               (_l("Bookings"), lambda o: format_html('<a class="va" href="{}?q={}">{}</a>', reverse("dash_manage", args=["bookings"]), o.title, o.n_book)),
               (_l("Status"), lambda o: format_html("{} {}", pill(_l("Active"), "ok") if o.active else pill(_l("Hidden"), "mut"), pill(_l("Featured"), "info") if o.featured else ""))]
    actions = {"active": (_l("Show / hide"), "", toggle("active", "is now visible", "is now hidden")), "feature": (_l("Feature / unfeature"), "", toggle("featured", "featured", "unfeatured"))}

@register("destinations")
class Destinations(Resource):
    title, icon, nav, model = _l("Honeymoon Destinations"), "i-palm", "honeymoon", Destination
    form = model_form(Destination, ["name", "slug", "country", "kind", "region", "tagline", "description", "image", "from_price", "days", "nights", "features",
                                    "rating", "reviews", "featured", "active", "order"], widgets={"description": AREA(3), "features": AREA(3)})
    search, ordering = ["name", "country"], ["order", "name"]
    filters = [("kind", _l("All types"), lambda: Destination.KINDS, lambda qs, v: qs.filter(kind=v)),
               ("region", _l("All regions"), lambda: Destination.REGIONS, lambda qs, v: qs.filter(region=v))]
    def queryset(self): return Destination.objects.annotate(n_pkg=Count("packages"))
    row_link = lambda self, o: o.get_absolute_url()
    columns = [("", thumb("image")), (_l("Destination"), bold("name", lambda o: f"{o.country} · {o.get_kind_display()}")), (_l("From"), money("from_price")),
               (_l("Packages"), lambda o: format_html('<a class="va" href="{}?destination={}">{}</a>', reverse("dash_manage", args=["packages"]), o.pk, o.n_pkg)),
               (_l("Rating"), lambda o: f"{o.rating} ({o.reviews:,})"),
               (_l("Status"), lambda o: format_html("{} {}", pill(_l("Active"), "ok") if o.active else pill(_l("Hidden"), "mut"), pill(_l("On home page"), "info") if o.featured else ""))]
    actions = {"active": (_l("Show / hide"), "", toggle("active", "is now visible", "is now hidden")), "feature": (_l("Show on home page / remove"), "", toggle("featured", "is on the home page", "removed from the home page"))}

@register("package-photos")
class PackagePhotos(Resource):
    title, icon, nav, model = _l("Package Photos"), "i-image", "honeymoon", PackagePhoto
    form = model_form(PackagePhoto, ["package", "image", "caption", "order"])
    search = ["caption", "package__title"]
    filters = [("package", _l("All packages"), lambda: [(str(p.pk), p.title) for p in Package.objects.all()], lambda qs, v: qs.filter(package_id=v))]
    ordering = ["package__title", "order", "pk"]
    def queryset(self): return PackagePhoto.objects.select_related("package")
    columns = [("", thumb("image")), (_l("Package"), lambda o: o.package.title), (_l("Caption"), lambda o: o.caption or "—"), (_l("Order"), lambda o: o.order)]

@register("package-reviews")
class PackageReviews(Resource):
    title, icon, nav, model = _l("Package Reviews"), "i-star", "honeymoon", PackageReview
    can_add = can_edit = False
    search = ["comment", "package__title", "user__username"]
    ordering = ["-created"]
    def queryset(self): return PackageReview.objects.select_related("package", "user__member")
    columns = [(_l("Member"), lambda o: user_label(o.user)), (_l("Package"), lambda o: o.package.title), (_l("Rating"), lambda o: "★" * o.rating),
               (_l("Comment"), lambda o: (o.comment or "—")[:120]), (_l("Date"), when("created"))]

# ---------- payments ----------
def complete_payment(o, r):
    if o.status != "pending": return "was not pending"
    o.status = "completed"; o.save(update_fields=["status"])
    if o.kind == "advert" and o.ad_order_id:   # an Advertise with us payment: publish (or extend) the advert
        ad = o.ad_order.publish(r)
        return f"confirmed, and the advert is live until {ad.expires:%d %b %Y}"
    if o.kind == "banner" and o.banner_order_id:
        b = o.banner_order; b.paid(r)
        return f"confirmed; the banner is live until {b.expires:%d %b %Y}" if b.is_live else "confirmed; approve the banner under Banners to publish it"
    activated = o.activate()
    if activated and o.user_id:
        Notification.objects.create(user=o.user, title=f"{o.plan.name} plan activated", link=reverse("m_membership"),
                                    body=f"Thank you! Your {o.plan.name} plan is active until {o.user.member.premium_until:%d %b %Y}.")
        return f"confirmed, and {o.user.member.name} is on the {o.plan.name} plan until {o.user.member.premium_until:%d %b %Y}"
    return "confirmed, but no plan was activated: " + why_no_plan(o)

def why_no_plan(o):
    """Why confirming this payment did not put anyone on a plan - said plainly, so nobody is left guessing."""
    if o.kind != "premium": return f"it is a {o.get_kind_display().lower()}, not a membership payment"
    if not o.plan_id: return "no plan is set on it, so edit it and choose one"
    if not o.user_id: return "it is not linked to a member, so edit it and choose the member"
    return "the payer's account has no member profile"

def refund_payment(o, r):
    if o.status != "completed": return "was not completed"
    o.status = "refunded"; o.save(update_fields=["status"]); return "refunded"

@register("payments")
class Payments(Resource):
    title, icon, nav, model = _l("All Transactions"), "i-coins", "payments", Payment
    can_add = can_delete = False
    form = PaymentForm
    search = ["invoice_no", "payer_name", "payer_phone", "reference", "description"]
    filters = [("status", _l("All statuses"), lambda: list(Payment.STATUS), lambda qs, v: qs.filter(status=v)),
               ("kind", _l("All types"), lambda: list(Payment.KINDS), lambda qs, v: qs.filter(kind=v)),
               ("gateway", _l("All gateways"), lambda: list(Payment.GATEWAYS), lambda qs, v: qs.filter(gateway=v))]
    ordering = ["-created"]
    per_page = 25
    def queryset(self): return Payment.objects.select_related("plan")
    columns = [(_l("Invoice"), bold("invoice_no", lambda o: o.created.strftime("%d %b %Y %H:%M"))), (_l("Payer"), lambda o: format_html('<b class="mn">{}</b><small class="mc">{}</small>', o.payer_name, o.payer_phone)),
               (_l("For"), lambda o: o.description or o.get_kind_display()), (_l("Gateway"), lambda o: format_html("{}<small class=\"mc\">{}</small>", o.get_gateway_display(), o.reference or "")),
               (_l("Amount"), money("amount")),
               (_l("Status"), lambda o: pill(o.get_status_display(), {"completed": "ok", "pending": "warn"}.get(o.status, "bad"))),
               ("", lambda o: format_html('<a class="va" href="{}" target="_blank">Receipt</a>', reverse("dash_receipt", args=[o.pk])) if o.status == "completed" else "")]
    actions = {"complete": (_l("Approve payment"), "", complete_payment), "refund": (_l("Refund"), "dang", refund_payment)}
    front = {"complete": lambda o: o.status == "pending"}        # approving is one click, not hidden in the menu

# ---------- members (add / edit only; the list is the Members Management page) ----------
@register("members")
class Members(Resource):
    title, icon, nav, model = _l("Member"), "m-people", "members", Member
    form = MemberAdminForm
    def after_save(self, obj, request, created):
        if created and not obj.joined: obj.joined = timezone.now(); obj.save(update_fields=["joined"])

# ---------- audit log (owner only, read only) ----------
ACTIONS = {1: (_l("Added"), "ok"), 2: (_l("Changed"), "info"), 3: (_l("Deleted"), "bad")}
@register("audit")
class Audit(Resource):
    title, icon, nav, model = _l("Audit Logs"), "m-doc", "audit", LogEntry
    can_add = can_edit = can_delete = False; owner_only = True; per_page = 30
    search = ["object_repr", "change_message", "user__username"]
    filters = [("action", _l("All actions"), lambda: [("1", _l("Added")), ("2", _l("Changed")), ("3", _l("Deleted"))], lambda qs, v: qs.filter(action_flag=int(v)))]
    ordering = ["-action_time"]
    def queryset(self): return LogEntry.objects.select_related("user", "content_type")
    columns = [(_l("When"), when("action_time", "%d %b %Y %H:%M")), (_l("Staff"), lambda o: user_label(o.user)),
               (_l("Action"), lambda o: pill(*ACTIONS.get(o.action_flag, ("—", "mut")))), (_l("Type"), lambda o: o.content_type.name.title() if o.content_type else "—"),
               (_l("Item"), lambda o: o.object_repr), (_l("Details"), lambda o: o.get_change_message() or "—")]

SIDEBAR = {  # nav key -> resources listed together in a section header
    "events": ["events", "event-categories", "registrations"], "plans": ["plans", "perks"],
    "content": ["articles", "article-categories", "home-strips"], "comms": ["templates", "broadcasts"],
    "support": ["tickets", "reports", "inquiries"], "marketing": ["ad-orders", "ad-packages", "adverts", "vendors", "service-categories"],
    "honeymoon": ["bookings", "packages", "destinations", "package-photos", "package-reviews"],
}
