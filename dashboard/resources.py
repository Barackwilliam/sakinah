"""Everything the client manages from the dashboard, described once: list columns, filters, form fields and row actions.
The generic views in views_manage.py turn each Resource into list / add / edit / delete pages, so the client never needs
the developer-only Django admin."""
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
from core.models import (Advert, Article, ArticleCategory, Booking, Broadcast, Destination, Event, Package, PackagePhoto, PackageReview, EventCategory, EventRegistration, FeatureStrip, Inquiry,
                         Member, MessageTemplate, Notification, Payment, Plan, PremiumPerk, Report, ServiceCategory, SupportTicket, Vendor)

# ---------- small column helpers ----------
def thumb(field):
    def f(o):
        img = getattr(o, field)
        return format_html('<span class="th2"><img src="{}" alt=""></span>', img.url) if img else mark_safe('<span class="th2"></span>')
    return f

def pill(text, tone):
    return format_html('<span class="pill {}">{}</span>', tone, text)

def yesno(field, yes="Yes", no="No", tone_yes="ok", tone_no="mut"):
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
        form.base_fields["slug"].help_text = "Leave empty to create it from the " + attrs["slug_from"] + "."
        return pretty_files(form)
    return pretty_files(type(f"{model.__name__}Form", (forms.ModelForm,), attrs))

class MemberAdminForm(forms.ModelForm):
    city = forms.ChoiceField(choices=[(c, c) for c in LOCATIONS])
    class Meta:
        model = Member
        fields = ["name", "age", "gender", "city", "occupation", "education", "marital_status", "religion", "practice", "phone", "headline",
                  "bio", "interests", "photo", "verified", "featured", "status", "plan", "premium_until", "compatibility"]
        widgets = {"bio": AREA(4), "premium_until": DATE}
        help_texts = {"premium_until": "The plan is active until this date. Leave empty for a free member.",
                      "compatibility": "Match score (0-100) shown on suggestions.", "status": "Rejected and suspended members are hidden from everyone."}
pretty_files(MemberAdminForm)

# ---------- resource definition ----------
class Resource:
    title = ""; icon = "m-doc"; nav = ""; model = None; form = None
    columns = []; search = []; filters = []; ordering = ["-pk"]
    can_add = can_edit = can_delete = True; owner_only = False; per_page = 20
    actions = {}          # name -> (label, tone, fn(obj, request) -> message)
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
    title, icon, nav, model = "Events", "m-cal", "events", Event
    form = model_form(Event, ["title", "category", "date", "start_time", "end_time", "city", "capacity", "attendees", "tags", "description", "image"],
                      widgets={"date": DATE, "start_time": TIME, "end_time": TIME, "description": AREA(3)},
                      help={"attendees": "People already going before online registration (walk-ins).", "capacity": "Leave empty for no limit."})
    search = ["title", "city", "tags"]
    filters = [("when", "All dates", lambda: [("upcoming", "Upcoming"), ("past", "Past")],
                lambda qs, v: qs.filter(date__gte=date.today()) if v == "upcoming" else qs.filter(date__lt=date.today())),
               ("category", "All categories", lambda: [(str(c.pk), c.name) for c in EventCategory.objects.all()], lambda qs, v: qs.filter(category_id=v))]
    ordering = ["-date"]
    def queryset(self): return Event.objects.select_related("category").annotate(reg_count=Count("registrations"))
    columns = [("", thumb("image")), ("Event", bold("title", lambda o: o.category.name if o.category else "")), ("Date", when("date")),
               ("Time", lambda o: f"{o.start_time:%H:%M}" if o.start_time else "—"), ("Location", lambda o: o.city),
               ("Registrations", lambda o: format_html('<a class="va" href="{}?event={}">{}</a>', reverse("dash_manage", args=["registrations"]), o.pk, o.reg_count)),
               ("Seats", lambda o: "Open" if o.capacity is None else f"{o.seats_left} of {o.capacity} left")]

@register("event-categories")
class EventCategories(Resource):
    title, icon, nav, model = "Event Categories", "m-cal", "events", EventCategory
    form = model_form(EventCategory, ["name", "slug", "order"])
    search, ordering = ["name"], ["order", "pk"]
    columns = [("Name", bold("name")), ("Slug", lambda o: o.slug), ("Events", lambda o: o.events.count()), ("Order", lambda o: o.order)]

@register("registrations")
class Registrations(Resource):
    title, icon, nav, model = "Event Registrations", "m-ticket", "events", EventRegistration
    can_add = can_edit = False
    search = ["event__title", "user__username", "user__email", "user__member__name"]
    filters = [("event", "All events", lambda: [(str(e.pk), f"{e.title} ({e.date:%d %b})") for e in Event.objects.order_by("-date")], lambda qs, v: qs.filter(event_id=v))]
    ordering = ["-created"]
    def queryset(self): return EventRegistration.objects.select_related("event", "user__member")
    columns = [("Member", lambda o: format_html('<b class="mn">{}</b><small class="mc">{}</small>', user_label(o.user), o.user.email)),
               ("Phone", lambda o: getattr(getattr(o.user, "member", None), "phone", "") or "—"),
               ("Event", lambda o: o.event.title), ("Event date", lambda o: o.event.date.strftime("%d %b %Y")), ("Registered", when("created", "%d %b %Y %H:%M"))]

# ---------- membership plans ----------
@register("plans")
class Plans(Resource):
    title, icon, nav, model = "Membership Plans", "m-crown", "plans", Plan
    form = model_form(Plan, ["name", "price", "period", "order", "tagline", "features", "popular", "icon"], widgets={"features": AREA(8)},
                      help={"features": "One feature per line. Start a line with - for a feature the plan does NOT include. Write 'All Silver features' to include the previous plan."})
    search, ordering = ["name"], ["order", "pk"]
    columns = [("", thumb("icon")), ("Plan", bold("name", lambda o: o.tagline)), ("Price", lambda o: f"TSh {o.price:,} {o.period}"),
               ("Active members", lambda o: o.members.filter(premium_until__gte=date.today()).count() if o.price else "—"),
               ("Most popular", yesno("popular", "Yes", "—")), ("Order", lambda o: o.order)]

@register("perks")
class Perks(Resource):
    title, icon, nav, model = "Premium Perks", "m-star", "plans", PremiumPerk
    form = model_form(PremiumPerk, ["text", "order"])
    search, ordering = ["text"], ["order", "pk"]
    columns = [("Perk", lambda o: o.text), ("Order", lambda o: o.order)]

# ---------- content ----------
@register("articles")
class Articles(Resource):
    title, icon, nav, model = "Articles", "m-book", "content", Article
    form = model_form(Article, ["title", "slug", "category", "author", "published", "featured", "image", "excerpt", "body", "tags"],
                      widgets={"published": DATE, "excerpt": AREA(2), "body": AREA(14)}, slug_from="title",
                      help={"body": "Separate paragraphs with an empty line. Start a line with ## for a heading."})
    search = ["title", "author", "tags"]
    filters = [("category", "All categories", lambda: [(str(c.pk), c.name) for c in ArticleCategory.objects.all()], lambda qs, v: qs.filter(category_id=v))]
    def queryset(self): return Article.objects.select_related("category")
    ordering = ["-published", "-pk"]
    columns = [("", thumb("image")), ("Article", bold("title", lambda o: o.category.name if o.category else "")), ("Author", lambda o: o.author or "—"),
               ("Published", when("published")), ("Views", lambda o: f"{o.views:,}"), ("Featured", yesno("featured", "Featured", "—", "info"))]
    actions = {"feature": ("Feature / unfeature", "", toggle("featured", "featured", "unfeatured"))}

@register("article-categories")
class ArticleCategories(Resource):
    title, icon, nav, model = "Article Categories", "m-book", "content", ArticleCategory
    form = model_form(ArticleCategory, ["name", "slug", "icon", "order"])
    search, ordering = ["name"], ["order", "pk"]
    columns = [("Name", bold("name")), ("Articles", lambda o: o.articles.count()), ("Order", lambda o: o.order)]

@register("home-strips")
class HomeStrips(Resource):
    title, icon, nav, model = "Home Page Highlights", "m-home", "content", FeatureStrip
    form = model_form(FeatureStrip, ["title", "text", "icon", "order"])
    ordering = ["order", "pk"]
    note = "The short feature boxes shown on the home page."
    columns = [("Title", bold("title")), ("Text", lambda o: o.text), ("Order", lambda o: o.order)]

# ---------- communication ----------
@register("templates")
class Templates(Resource):
    title, icon, nav, model = "Message Templates", "m-doc", "comms", MessageTemplate
    form = model_form(MessageTemplate, ["name", "description", "subject", "body", "icon", "color", "order"], widgets={"body": AREA(8)},
                      help={"body": "Use {name} for the member's name."})
    search, ordering = ["name", "subject"], ["order", "pk"]
    columns = [("Template", bold("name", lambda o: o.description)), ("Subject", lambda o: o.subject),
               ("", lambda o: format_html('<a class="va" href="{}?template={}">Use</a>', reverse("dash_comms"), o.pk))]

@register("broadcasts")
class Broadcasts(Resource):
    title, icon, nav, model = "Message History", "m-send", "comms", Broadcast
    can_add = can_edit = False
    search = ["subject", "body"]
    filters = [("channel", "All channels", lambda: list(Broadcast.CHANNELS), lambda qs, v: qs.filter(channel=v)),
               ("status", "All statuses", lambda: [("sent", "Sent"), ("draft", "Draft")], lambda qs, v: qs.filter(status=v))]
    ordering = ["-created"]
    columns = [("Subject", bold("subject", lambda o: o.get_channel_display())), ("Recipients", lambda o: f"{o.recipients:,}"),
               ("Status", lambda o: pill(o.get_status_display(), "ok" if o.status == "sent" else "warn")),
               ("Created", when("created", "%d %b %Y %H:%M")), ("By", lambda o: user_label(o.created_by))]

# ---------- support ----------
@register("tickets")
class Tickets(Resource):
    title, icon, nav, model = "Support Tickets", "m-headset", "support", SupportTicket
    can_add = False
    form = model_form(SupportTicket, ["reply", "status"], widgets={"reply": AREA(6)},
                      help={"reply": "The member gets this answer as a notification in their dashboard."})
    search = ["subject", "message", "user__username", "user__email"]
    filters = [("status", "All statuses", lambda: list(SupportTicket.STATUS), lambda qs, v: qs.filter(status=v)),
               ("kind", "All types", lambda: list(SupportTicket.KINDS), lambda qs, v: qs.filter(kind=v))]
    ordering = ["status", "-created"]
    def queryset(self): return SupportTicket.objects.select_related("user__member")
    columns = [("Subject", lambda o: format_html('<b class="mn">{}</b><small class="mc">{}</small>', o.subject, o.message[:90])),
               ("Type", lambda o: o.get_kind_display()), ("From", lambda o: user_label(o.user)),
               ("Attachment", lambda o: format_html('<a class="va" href="{}" target="_blank">Open file</a>', o.attachment.url) if o.attachment else "—"),
               ("Received", when("created", "%d %b %Y %H:%M")),
               ("Status", lambda o: pill("Answered" if o.reply and o.status == "closed" else o.get_status_display(), "warn" if o.status == "open" else "ok"))]
    actions = {"close": ("Close / reopen", "", lambda o, r: (set_field("status", "closed" if o.status == "open" else "open", "updated")(o, r)))}
    def after_save(self, obj, request, created):
        if obj.reply and obj.user_id and not obj.replied_at:
            obj.replied_at = timezone.now(); obj.status = "closed"; obj.save(update_fields=["replied_at", "status"])
            Notification.objects.create(user=obj.user, title=f"Support replied: {obj.subject}"[:120], body=obj.reply, link=reverse("m_help"))
        if obj.kind == "verification" and obj.status == "closed" and request.POST.get("verify_member") and obj.user_id and hasattr(obj.user, "member"):
            obj.user.member.verified = True; obj.user.member.save(update_fields=["verified"])

@register("reports")
class Reports(Resource):
    title, icon, nav, model = "Member Reports", "m-flag", "support", Report
    can_add = can_edit = False
    search = ["member__name", "details", "reporter__username"]
    filters = [("resolved", "Open and resolved", lambda: [("0", "Open"), ("1", "Resolved")], lambda qs, v: qs.filter(resolved=v == "1"))]
    ordering = ["resolved", "-created"]
    def queryset(self): return Report.objects.select_related("member", "reporter")
    columns = [("Reported member", lambda o: format_html('<a href="{}" target="_blank"><b class="mn">{}</b></a><small class="mc">{}</small>', reverse("member", args=[o.member_id]), o.member.name, o.member.city)),
               ("Reason", lambda o: o.get_reason_display()), ("Details", lambda o: (o.details or "—")[:120]), ("By", lambda o: user_label(o.reporter)),
               ("Date", when("created")), ("Status", lambda o: pill("Resolved", "ok") if o.resolved else pill("Open", "bad"))]
    actions = {"resolve": ("Mark resolved / open", "", toggle("resolved", "marked resolved", "reopened")),
               "suspend": ("Suspend this member", "dang", lambda o, r: (set_field("status", "suspended", "suspended")(o.member, r)))}

@register("inquiries")
class Inquiries(Resource):
    title, icon, nav, model = "Vendor Inquiries", "m-mail", "support", Inquiry
    can_add = can_edit = False
    search = ["name", "phone", "message", "advert__title"]
    filters = [("handled", "All", lambda: [("0", "New"), ("1", "Handled")], lambda qs, v: qs.filter(handled=v == "1"))]
    ordering = ["handled", "-created"]
    def queryset(self): return Inquiry.objects.select_related("advert")
    columns = [("Customer", lambda o: format_html('<b class="mn">{}</b><small class="mc">{}</small>', o.name, o.phone)), ("Service", lambda o: o.advert.title),
               ("Type", lambda o: o.get_kind_display()), ("Event date", when("event_date")),
               ("Message", lambda o: (o.message or "—")[:100]), ("Received", when("created")), ("Status", lambda o: pill("Handled", "ok") if o.handled else pill("New", "warn"))]
    actions = {"handled": ("Mark handled / new", "", toggle("handled", "marked handled", "marked new"))}

# ---------- marketing ----------
@register("adverts")
class Adverts(Resource):
    title, icon, nav, model = "Adverts", "i-mega", "marketing", Advert
    form = model_form(Advert, ["title", "slug", "category", "vendor", "city", "price", "price_unit", "negotiable", "image", "description", "highlights",
                               "includes", "extras", "availability", "details", "map_query", "featured", "active"],
                      widgets={"description": AREA(5), "highlights": AREA(3), "includes": AREA(3), "extras": AREA(3), "details": AREA(3)}, slug_from="title")
    search = ["title", "city", "vendor__name"]
    filters = [("category", "All categories", lambda: [(str(c.pk), c.name) for c in ServiceCategory.objects.all()], lambda qs, v: qs.filter(category_id=v)),
               ("active", "All", lambda: [("1", "Active"), ("0", "Hidden")], lambda qs, v: qs.filter(active=v == "1"))]
    ordering = ["-created"]
    def queryset(self): return Advert.objects.select_related("vendor", "category")
    row_link = lambda self, o: reverse("advert", args=[o.slug])
    columns = [("", thumb("image")), ("Advert", bold("title", lambda o: o.vendor.name)), ("Category", lambda o: o.category.name), ("Location", lambda o: o.city),
               ("Price", lambda o: f"TSh {o.price:,}" if o.price else "—"), ("Views", lambda o: f"{o.views:,}"),
               ("Status", lambda o: format_html("{} {}", pill("Active", "ok") if o.active else pill("Hidden", "mut"), pill("Featured", "info") if o.featured else ""))]
    actions = {"active": ("Show / hide", "", toggle("active", "is now visible", "is now hidden")), "feature": ("Feature / unfeature", "", toggle("featured", "featured", "unfeatured"))}

@register("vendors")
class Vendors(Resource):
    title, icon, nav, model = "Vendors", "m-briefcase", "marketing", Vendor
    form = model_form(Vendor, ["name", "slug", "city", "phone", "logo", "verified", "member_since", "why_choose"], widgets={"member_since": DATE, "why_choose": AREA(3)})
    search, ordering = ["name", "city"], ["name"]
    columns = [("", thumb("logo")), ("Vendor", bold("name", lambda o: o.phone)), ("City", lambda o: o.city), ("Adverts", lambda o: o.adverts.count()),
               ("Verified", yesno("verified", "Verified", "—"))]

@register("service-categories")
class ServiceCategories(Resource):
    title, icon, nav, model = "Service Categories", "m-grid", "marketing", ServiceCategory
    form = model_form(ServiceCategory, ["name", "slug", "blurb", "button_label", "image", "order"], widgets={"blurb": AREA(2)})
    search, ordering = ["name"], ["order", "pk"]
    columns = [("", thumb("image")), ("Category", bold("name", lambda o: o.blurb[:60])), ("Adverts", lambda o: Advert.objects.filter(category=o).count()), ("Order", lambda o: o.order)]

# ---------- honeymoon ----------
def booking_status(status, msg):
    def fn(o, r):
        o.status = status; o.save(update_fields=["status"])
        if o.user_id and status in ("confirmed", "cancelled"):
            Notification.objects.create(user=o.user, link=o.package.get_absolute_url(),
                title=f"Honeymoon booking {'confirmed' if status == 'confirmed' else 'cancelled'}: {o.package.title}",
                body="Hongera! Your honeymoon booking is confirmed. Our team will share the travel details with you." if status == "confirmed"
                     else "Your honeymoon booking request was cancelled. Contact us if you would like to choose other dates.")
        return msg
    return fn

BOOKING_TONES = {"new": "warn", "contacted": "info", "confirmed": "ok", "cancelled": "bad"}

@register("bookings")
class Bookings(Resource):
    title, icon, nav, model = "Honeymoon Bookings", "m-cal", "honeymoon", Booking
    can_add = False
    form = model_form(Booking, ["status", "travel_date", "couples", "name", "phone", "email", "message"], widgets={"travel_date": DATE, "message": AREA(3)})
    search = ["name", "phone", "email", "package__title"]
    filters = [("status", "All statuses", lambda: Booking.STATUS, lambda qs, v: qs.filter(status=v)),
               ("package__destination", "All destinations", lambda: [(str(d.pk), d.name) for d in Destination.objects.all()], lambda qs, v: qs.filter(package__destination_id=v))]
    ordering = ["-created"]
    def queryset(self): return Booking.objects.select_related("package__destination", "user")
    columns = [("Couple", lambda o: format_html('<b class="mn">{}</b><small class="mc">{}{}</small>', o.name, o.phone, f" · {o.email}" if o.email else "")),
               ("Package", lambda o: format_html('<a class="va" href="{}" target="_blank">{}</a><small class="mc">{}</small>', o.package.get_absolute_url(), o.package.title, o.package.destination.name)),
               ("Travel date", when("travel_date")), ("Couples", lambda o: o.couples), ("Estimated total", lambda o: f"TSh {o.total:,}"),
               ("Received", when("created", "%d %b %Y %H:%M")), ("Status", lambda o: pill(o.get_status_display(), BOOKING_TONES[o.status]))]
    actions = {"contacted": ("Mark contacted", "", booking_status("contacted", "marked contacted")),
               "confirmed": ("Confirm booking", "", booking_status("confirmed", "confirmed and the member notified")),
               "cancelled": ("Cancel booking", "dang", booking_status("cancelled", "cancelled"))}

@register("packages")
class Packages(Resource):
    title, icon, nav, model = "Honeymoon Packages", "i-gem", "honeymoon", Package
    form = model_form(Package, ["title", "slug", "destination", "location", "package_type", "badge", "badge_tone", "image", "price", "days", "nights", "stars",
                                "stay", "meals", "meals_detail", "extra", "extra_icon", "flights", "transfer", "romance", "overview", "highlights", "itinerary",
                                "inclusions", "exclusions", "accommodation", "activities", "important_info", "ideal_for", "rating", "reviews",
                                "discount", "free_addons", "all_inclusive", "featured", "active", "order"],
                      widgets={k: AREA(4) for k in ("overview", "highlights", "itinerary", "inclusions", "exclusions", "accommodation", "activities", "important_info", "ideal_for")},
                      slug_from="title")
    search = ["title", "location", "destination__name"]
    filters = [("destination", "All destinations", lambda: [(str(d.pk), d.name) for d in Destination.objects.all()], lambda qs, v: qs.filter(destination_id=v)),
               ("active", "All", lambda: [("1", "Active"), ("0", "Hidden")], lambda qs, v: qs.filter(active=v == "1"))]
    ordering = ["destination__order", "order", "pk"]
    def queryset(self): return Package.objects.select_related("destination").annotate(n_book=Count("bookings", distinct=True), n_photos=Count("photos", distinct=True))
    row_link = lambda self, o: o.get_absolute_url()
    columns = [("", thumb("image")), ("Package", bold("title", lambda o: f"{o.destination.name} · {o.days} days {o.nights} nights")), ("Price", money("price")),
               ("Badge", lambda o: o.badge or "—"),
               ("Photos", lambda o: format_html('<a class="va" href="{}?package={}">{}</a>', reverse("dash_manage", args=["package-photos"]), o.pk, o.n_photos)),
               ("Bookings", lambda o: format_html('<a class="va" href="{}?q={}">{}</a>', reverse("dash_manage", args=["bookings"]), o.title, o.n_book)),
               ("Status", lambda o: format_html("{} {}", pill("Active", "ok") if o.active else pill("Hidden", "mut"), pill("Featured", "info") if o.featured else ""))]
    actions = {"active": ("Show / hide", "", toggle("active", "is now visible", "is now hidden")), "feature": ("Feature / unfeature", "", toggle("featured", "featured", "unfeatured"))}

@register("destinations")
class Destinations(Resource):
    title, icon, nav, model = "Honeymoon Destinations", "i-palm", "honeymoon", Destination
    form = model_form(Destination, ["name", "slug", "country", "kind", "region", "tagline", "description", "image", "from_price", "days", "nights", "features",
                                    "rating", "reviews", "featured", "active", "order"], widgets={"description": AREA(3), "features": AREA(3)})
    search, ordering = ["name", "country"], ["order", "name"]
    filters = [("kind", "All types", lambda: Destination.KINDS, lambda qs, v: qs.filter(kind=v)),
               ("region", "All regions", lambda: Destination.REGIONS, lambda qs, v: qs.filter(region=v))]
    def queryset(self): return Destination.objects.annotate(n_pkg=Count("packages"))
    row_link = lambda self, o: o.get_absolute_url()
    columns = [("", thumb("image")), ("Destination", bold("name", lambda o: f"{o.country} · {o.get_kind_display()}")), ("From", money("from_price")),
               ("Packages", lambda o: format_html('<a class="va" href="{}?destination={}">{}</a>', reverse("dash_manage", args=["packages"]), o.pk, o.n_pkg)),
               ("Rating", lambda o: f"{o.rating} ({o.reviews:,})"),
               ("Status", lambda o: format_html("{} {}", pill("Active", "ok") if o.active else pill("Hidden", "mut"), pill("On home page", "info") if o.featured else ""))]
    actions = {"active": ("Show / hide", "", toggle("active", "is now visible", "is now hidden")), "feature": ("Show on home page / remove", "", toggle("featured", "is on the home page", "removed from the home page"))}

@register("package-photos")
class PackagePhotos(Resource):
    title, icon, nav, model = "Package Photos", "i-image", "honeymoon", PackagePhoto
    form = model_form(PackagePhoto, ["package", "image", "caption", "order"])
    search = ["caption", "package__title"]
    filters = [("package", "All packages", lambda: [(str(p.pk), p.title) for p in Package.objects.all()], lambda qs, v: qs.filter(package_id=v))]
    ordering = ["package__title", "order", "pk"]
    def queryset(self): return PackagePhoto.objects.select_related("package")
    columns = [("", thumb("image")), ("Package", lambda o: o.package.title), ("Caption", lambda o: o.caption or "—"), ("Order", lambda o: o.order)]

@register("package-reviews")
class PackageReviews(Resource):
    title, icon, nav, model = "Package Reviews", "i-star", "honeymoon", PackageReview
    can_add = can_edit = False
    search = ["comment", "package__title", "user__username"]
    ordering = ["-created"]
    def queryset(self): return PackageReview.objects.select_related("package", "user__member")
    columns = [("Member", lambda o: user_label(o.user)), ("Package", lambda o: o.package.title), ("Rating", lambda o: "★" * o.rating),
               ("Comment", lambda o: (o.comment or "—")[:120]), ("Date", when("created"))]

# ---------- payments ----------
def complete_payment(o, r):
    if o.status != "pending": return "was not pending"
    o.status = "completed"; o.save(update_fields=["status"]); activated = o.activate()
    if activated and o.user_id:
        Notification.objects.create(user=o.user, title=f"{o.plan.name} plan activated", link=reverse("m_membership"),
                                    body=f"Thank you! Your {o.plan.name} plan is active until {o.user.member.premium_until:%d %b %Y}.")
    return "confirmed" + (" and the plan activated" if activated else "")

def refund_payment(o, r):
    if o.status != "completed": return "was not completed"
    o.status = "refunded"; o.save(update_fields=["status"]); return "refunded"

@register("payments")
class Payments(Resource):
    title, icon, nav, model = "All Transactions", "i-coins", "payments", Payment
    can_add = can_edit = can_delete = False
    search = ["invoice_no", "payer_name", "payer_phone", "reference", "description"]
    filters = [("status", "All statuses", lambda: list(Payment.STATUS), lambda qs, v: qs.filter(status=v)),
               ("kind", "All types", lambda: list(Payment.KINDS), lambda qs, v: qs.filter(kind=v)),
               ("gateway", "All gateways", lambda: list(Payment.GATEWAYS), lambda qs, v: qs.filter(gateway=v))]
    ordering = ["-created"]
    per_page = 25
    def queryset(self): return Payment.objects.select_related("plan")
    columns = [("Invoice", bold("invoice_no", lambda o: o.created.strftime("%d %b %Y %H:%M"))), ("Payer", lambda o: format_html('<b class="mn">{}</b><small class="mc">{}</small>', o.payer_name, o.payer_phone)),
               ("For", lambda o: o.description or o.get_kind_display()), ("Gateway", lambda o: format_html("{}<small class=\"mc\">{}</small>", o.get_gateway_display(), o.reference or "")),
               ("Amount", money("amount")),
               ("Status", lambda o: pill(o.get_status_display(), {"completed": "ok", "pending": "warn"}.get(o.status, "bad"))),
               ("", lambda o: format_html('<a class="va" href="{}" target="_blank">Receipt</a>', reverse("dash_receipt", args=[o.pk])) if o.status == "completed" else "")]
    actions = {"complete": ("Confirm payment", "", complete_payment), "refund": ("Refund", "dang", refund_payment)}

# ---------- members (add / edit only; the list is the Members Management page) ----------
@register("members")
class Members(Resource):
    title, icon, nav, model = "Member", "m-people", "members", Member
    form = MemberAdminForm
    def after_save(self, obj, request, created):
        if created and not obj.joined: obj.joined = timezone.now(); obj.save(update_fields=["joined"])

# ---------- audit log (owner only, read only) ----------
ACTIONS = {1: ("Added", "ok"), 2: ("Changed", "info"), 3: ("Deleted", "bad")}
@register("audit")
class Audit(Resource):
    title, icon, nav, model = "Audit Logs", "m-doc", "audit", LogEntry
    can_add = can_edit = can_delete = False; owner_only = True; per_page = 30
    search = ["object_repr", "change_message", "user__username"]
    filters = [("action", "All actions", lambda: [("1", "Added"), ("2", "Changed"), ("3", "Deleted")], lambda qs, v: qs.filter(action_flag=int(v)))]
    ordering = ["-action_time"]
    def queryset(self): return LogEntry.objects.select_related("user", "content_type")
    columns = [("When", when("action_time", "%d %b %Y %H:%M")), ("Staff", lambda o: user_label(o.user)),
               ("Action", lambda o: pill(*ACTIONS.get(o.action_flag, ("—", "mut")))), ("Type", lambda o: o.content_type.name.title() if o.content_type else "—"),
               ("Item", lambda o: o.object_repr), ("Details", lambda o: o.get_change_message() or "—")]

SIDEBAR = {  # nav key -> resources listed together in a section header
    "events": ["events", "event-categories", "registrations"], "plans": ["plans", "perks"],
    "content": ["articles", "article-categories", "home-strips"], "comms": ["templates", "broadcasts"],
    "support": ["tickets", "reports", "inquiries"], "marketing": ["adverts", "vendors", "service-categories"],
    "honeymoon": ["bookings", "packages", "destinations", "package-photos", "package-reviews"],
}
