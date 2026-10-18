"""Email over HTTPS APIs. Render's free plan blocks SMTP ports (25, 465, 587), so password-reset and other emails are sent
through Brevo or Resend instead, both of which have free plans. Pick one by setting BREVO_API_KEY or RESEND_API_KEY."""
import json
import logging
import urllib.request
from email.utils import parseaddr
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

log = logging.getLogger(__name__)

class _ApiBackend(BaseEmailBackend):
    url = ""
    def headers(self): return {}
    def payload(self, sender, to, subject, text, html): return {}

    def send_messages(self, messages):
        sent = 0
        for m in messages:
            html = next((body for body, mime in getattr(m, "alternatives", []) if mime == "text/html"), None)
            name, addr = parseaddr(m.from_email or settings.DEFAULT_FROM_EMAIL)
            to = [parseaddr(t)[1] for t in m.recipients()]
            data = json.dumps(self.payload((name, addr), to, m.subject, m.body, html)).encode()
            req = urllib.request.Request(self.url, data=data, method="POST",
                                         headers={"Content-Type": "application/json", "Accept": "application/json", **self.headers()})
            try:
                with urllib.request.urlopen(req, timeout=getattr(settings, "EMAIL_TIMEOUT", 15)) as r:
                    if 200 <= r.status < 300: sent += 1
            except Exception as e:
                detail = e.read().decode(errors="replace")[:300] if hasattr(e, "read") else str(e)
                log.error("Email to %s failed: %s", to, detail)
                if not self.fail_silently: raise RuntimeError(f"Email could not be sent: {detail}") from e
        return sent

class BrevoBackend(_ApiBackend):
    url = "https://api.brevo.com/v3/smtp/email"
    def headers(self): return {"api-key": settings.BREVO_API_KEY}
    def payload(self, sender, to, subject, text, html):
        p = {"sender": {"name": sender[0] or "Sakinah", "email": sender[1]}, "to": [{"email": t} for t in to], "subject": subject, "textContent": text}
        if html: p["htmlContent"] = html
        return p

class ResendBackend(_ApiBackend):
    url = "https://api.resend.com/emails"
    def headers(self): return {"Authorization": f"Bearer {settings.RESEND_API_KEY}"}
    def payload(self, sender, to, subject, text, html):
        p = {"from": f"{sender[0]} <{sender[1]}>" if sender[0] else sender[1], "to": to, "subject": subject, "text": text}
        if html: p["html"] = html
        return p
