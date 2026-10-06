from datetime import timedelta
from django.utils import timezone
from .models import Member

class LastSeenMiddleware:
    """Marks the signed-in member as seen, at most once a minute, for the "Online sasa" badge."""
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        if request.user.is_authenticated:
            now = timezone.now()
            Member.objects.filter(user=request.user).exclude(last_seen__gt=now - timedelta(minutes=1)).update(last_seen=now)
        return self.get_response(request)
