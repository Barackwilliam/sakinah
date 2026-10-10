import calendar
from collections import Counter
from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from .forms import CommentForm
from .models import Article, ArticleCategory, Event, EventCategory, EventRegistration, Plan, PremiumPerk
from .forms import LOCATIONS
from .views import safe_next

# ----- articles -----
def articles(request):
    q, cat, author, tag, sort = (request.GET.get(k, "") for k in ("q", "cat", "author", "tag", "sort"))
    qs = Article.objects.select_related("category").annotate(n_comments=Count("comments"))
    if q: qs = qs.filter(Q(title__icontains=q) | Q(excerpt__icontains=q) | Q(body__icontains=q))
    if cat: qs = qs.filter(category__slug=cat)
    if author: qs = qs.filter(author=author)
    if tag: qs = qs.filter(tags__icontains=tag)
    qs = qs.order_by("-views", "-published") if sort == "popular" else qs.order_by("-published", "-pk")
    params = request.GET.copy(); params.pop("page", None)
    tags = Counter(t for a in Article.objects.only("tags") for t in a.tag_list)
    return render(request, "articles.html", {
        "page": Paginator(qs, 6).get_page(request.GET.get("page")), "qs": params.urlencode(), "f": request.GET,
        "categories": ArticleCategory.objects.annotate(n=Count("articles")).order_by("order", "pk"), "total": Article.objects.count(),
        "authors": Article.objects.order_by("author").values_list("author", flat=True).distinct(),
        "tags": [t for t, _ in tags.most_common(12)],
        "featured": Article.objects.filter(featured=True).annotate(n_comments=Count("comments")).first(),
        "recent": Article.objects.order_by("-published", "-pk")[:4]})

def article(request, slug):
    a = get_object_or_404(Article.objects.select_related("category"), slug=slug)
    form = CommentForm(request.POST or None)
    if request.method == "POST":
        if not request.user.is_authenticated: return redirect(f"{reverse('login')}?next={a.get_absolute_url()}")
        if form.is_valid():
            form.instance.article, form.instance.user = a, request.user; form.save()
            messages.success(request, "Comment posted.")
            return redirect(a.get_absolute_url() + "#comments")
    else:
        Article.objects.filter(pk=a.pk).update(views=F("views") + 1)
    return render(request, "article.html", {"a": a, "views": a.views + 1, "form": form,
        "comments": a.comments.select_related("user__member"), "recent": Article.objects.exclude(pk=a.pk).order_by("-published")[:4],
        "related": Article.objects.filter(category=a.category).exclude(pk=a.pk)[:3]})

# ----- events -----
def events(request):
    q, cat, city, when = (request.GET.get(k, "") for k in ("q", "cat", "city", "when"))
    today = date.today()
    qs = Event.objects.select_related("category").annotate(reg_count=Count("registrations"))
    qs = qs.filter(date__lt=today).order_by("-date") if when == "past" else (qs if when == "all" else qs.filter(date__gte=today)).order_by("date", "pk")
    if q: qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if cat: qs = qs.filter(category__slug=cat)
    if city: qs = qs.filter(city=city)
    # calendar: the requested month, else the month of the next event, else this month
    try: y, m = map(int, request.GET.get("month", "").split("-"))
    except ValueError:
        nxt = Event.objects.filter(date__gte=today).first()
        y, m = (nxt.date.year, nxt.date.month) if nxt else (today.year, today.month)
    days = set(Event.objects.filter(date__year=y, date__month=m).values_list("date__day", flat=True))
    prev_m, next_m = (date(y - (m == 1), 12 if m == 1 else m - 1, 1), date(y + (m == 12), 1 if m == 12 else m + 1, 1))
    mine = set(request.user.event_registrations.values_list("event_id", flat=True)) if request.user.is_authenticated else set()
    return render(request, "events.html", {
        "events": qs, "f": request.GET, "mine": mine, "locations": sorted(set(LOCATIONS) | set(Event.objects.values_list("city", flat=True))),
        "categories": EventCategory.objects.annotate(n=Count("events")).order_by("order", "pk"), "total": Event.objects.count(),
        "cal": calendar.Calendar(firstweekday=6).monthdayscalendar(y, m), "cal_title": date(y, m, 1), "cal_days": days,
        "cal_today": today.day if (today.year, today.month) == (y, m) else 0,
        "prev_month": prev_m.strftime("%Y-%m"), "next_month": next_m.strftime("%Y-%m")})

@login_required
@require_POST
def event_register(request, pk):
    e = get_object_or_404(Event, pk=pk)
    mine = EventRegistration.objects.filter(event=e, user=request.user).exists()
    if not mine and e.date < date.today():
        messages.error(request, f"{e.title} has already taken place."); return redirect(safe_next(request) or reverse("events"))
    if not mine and e.seats_left == 0:
        messages.error(request, f"Sorry, {e.title} is fully booked."); return redirect(safe_next(request) or reverse("events"))
    reg, created = EventRegistration.objects.get_or_create(event=e, user=request.user)
    if not created: reg.delete()
    messages.success(request, f"You are registered for {e.title}. See you there!" if created else f"Your registration for {e.title} was cancelled.")
    return redirect(safe_next(request) or reverse("events"))

# ----- premium -----
def premium(request):
    return render(request, "premium.html", {"plans": Plan.objects.all(), "perks": PremiumPerk.objects.all()})
