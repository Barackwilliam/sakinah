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


class GZipPagesMiddleware(GZipMiddleware):
    """Compress pages, but not photos and other files that are already compressed."""
    def process_response(self, request, response):
        if response.get("Content-Type", "").startswith(("image/", "video/", "audio/", "application/pdf", "application/zip")):
            return response
        return super().process_response(request, response)
