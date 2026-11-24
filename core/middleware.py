from django.middleware.gzip import GZipMiddleware
from datetime import timedelta
from django.utils import timezone
from .models import Member

class LastSeenMiddleware:
    """Marks the signed-in member as seen, at most once a minute, for the "Online sasa" badge."""
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        if request.user.is_authenticated:
            from django.core.cache import cache
            # at most one database write per user per minute; other requests in that minute skip the query entirely
            if cache.add(f"seen:{request.user.pk}", 1, 60):
                now = timezone.now()
                Member.objects.filter(user=request.user).exclude(last_seen__gt=now - timedelta(minutes=1)).update(last_seen=now)
        return self.get_response(request)


class HideDjangoAdminMiddleware:
    """The built-in Django admin is the developer's back office. Anyone who is not a superuser gets a plain 404,
    so the client and members never see it exists. Sign in through /login/ first, then open the admin path."""
    def __init__(self, get_response):
        from django.conf import settings
        self.get_response, self.prefix = get_response, "/" + settings.ADMIN_URL
    def __call__(self, request):
        if request.path.startswith(self.prefix) and not (request.user.is_authenticated and request.user.is_superuser):
            from django.http import Http404
            raise Http404
        return self.get_response(request)


class AccountTypeMiddleware:
    """Advertisers and members have separate accounts. An advertiser who opens a member page (find a match, chats,
    the member dashboard) is taken to the advertiser dashboard instead."""
    MEMBER_ONLY = ("/account/", "/messages/", "/members/", "/likes/", "/notifications/", "/profile/", "/matches/")
    OPEN = ("/account/verify-email/", "/account/password-reset/", "/account/reset/")

    def __init__(self, get_response): self.get_response = get_response

    def __call__(self, request):
        p = request.path
        if p.startswith(self.MEMBER_ONLY) and not p.startswith(self.OPEN):
            from .models_ads import is_advertiser
            if is_advertiser(request.user):
                from django.shortcuts import redirect
                return redirect("ad_dashboard")
        return self.get_response(request)


class AdminHostMiddleware:
    """With ADMIN_HOST set, the admin dashboard and its login answer only on that address (admin.sakinah.co.tz):
    its home page is the admin login, and the public site's pages send visitors back to the main address. The main
    address sends /dashboard/ links over to the admin address."""
    ADMIN_PATHS = ("/dashboard/", "/static/", "/media/", "/i18n/", "/logout/", "/favicon", "/robots.txt")

    def __init__(self, get_response):
        from django.conf import settings
        self.get_response, self.host, self.site = get_response, settings.ADMIN_HOST, settings.SITE_URL
        self.admin_paths = self.ADMIN_PATHS + ("/" + settings.ADMIN_URL,)

    def __call__(self, request):
        if not self.host: return self.get_response(request)
        from django.shortcuts import redirect
        path, on_admin = request.get_full_path(), request.get_host().split(":")[0].lower() == self.host
        if on_admin:
            if request.path == "/": return redirect("/dashboard/")
            if not request.path.startswith(self.admin_paths): return redirect(self.site + path)
        elif request.path.startswith("/dashboard/"):
            return redirect(f"https://{self.host}{path}")
        return self.get_response(request)


class GZipPagesMiddleware(GZipMiddleware):
    """Compress pages, but not photos and other files that are already compressed."""
    def process_response(self, request, response):
        if response.get("Content-Type", "").startswith(("image/", "video/", "audio/", "application/pdf", "application/zip")):
            return response
        return super().process_response(request, response)


class TimingMiddleware:
    """Put how long the server took on the response, so a slow page can be told apart from a slow network.

    Read it in the browser's network tab under Timing, or in the response headers as `Server-Timing`.
    It carries no private data: a duration and a query count.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import time
        from django.db import connection
        count = _Counter()
        start = time.perf_counter()
        with connection.execute_wrapper(count):      # counts in production too, unlike connection.queries
            response = self.get_response(request)
        ms = (time.perf_counter() - start) * 1000
        try:
            response["Server-Timing"] = f'app;dur={ms:.0f}, db;dur={count.ms:.0f};desc="{count.n} queries"'
        except Exception:
            pass
        return response


class _Counter:
    """Counts the queries a request makes, and how long they take in total."""
    def __init__(self):
        self.n = self.ms = 0

    def __call__(self, execute, sql, params, many, context):
        import time
        self.n += 1
        t = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            self.ms += (time.perf_counter() - t) * 1000
