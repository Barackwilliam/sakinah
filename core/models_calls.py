"""Voice and video calls between members. The media flows browser to browser (WebRTC); the server only rings the other
person and passes the connection details (offer, answer and network candidates) between the two browsers."""
from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone

RING_SECONDS = 45   # an unanswered call becomes a missed call after this long

class Call(models.Model):
    KINDS = [("voice", "Voice call"), ("video", "Video call")]
    STATUS = [("ringing", "Ringing"), ("accepted", "In progress"), ("declined", "Declined"), ("ended", "Ended"),
              ("missed", "Missed"), ("cancelled", "Cancelled")]
    caller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calls_made")
    callee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calls_received")
    kind = models.CharField(max_length=5, choices=KINDS, default="voice")
    status = models.CharField(max_length=9, choices=STATUS, default="ringing")
    created = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ["-created"]
        indexes = [models.Index(fields=["callee", "status"]), models.Index(fields=["caller", "status"])]
    def __str__(self): return f"{self.get_kind_display()} {self.caller} -> {self.callee} ({self.status})"
    @property
    def live(self): return self.status in ("ringing", "accepted")
    @property
    def seconds(self):
        if not self.answered_at: return 0
        return int(((self.ended_at or timezone.now()) - self.answered_at).total_seconds())
    @property
    def duration_text(self):
        s = self.seconds
        return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"
    def expired(self):
        return self.status == "ringing" and self.created < timezone.now() - timedelta(seconds=RING_SECONDS)

class CallSignal(models.Model):
    """One message between the two browsers while they connect (offer, answer or a network candidate)."""
    KINDS = [("offer", "Offer"), ("answer", "Answer"), ("ice", "Network candidate")]
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name="signals")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=6, choices=KINDS)
    data = models.TextField(max_length=20000)
    created = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["pk"]
