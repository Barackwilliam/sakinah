"""ICE servers for calls. STUN finds each browser's public address; TURN relays the call when the two networks cannot reach each
other directly (common on mobile data). Set one of:
- CLOUDFLARE_TURN_KEY_ID + CLOUDFLARE_TURN_API_TOKEN (Cloudflare Realtime TURN, 1,000 GB free each month), or
- TURN_URLS + TURN_USERNAME + TURN_CREDENTIAL (e.g. the static credentials from metered.ca)."""
import json
import logging
import urllib.request
from django.conf import settings
from django.core.cache import cache

log = logging.getLogger(__name__)
STUN = [{"urls": ["stun:stun.cloudflare.com:3478", "stun:stun.l.google.com:19302"]}]

def _cloudflare():
    key, token = getattr(settings, "CLOUDFLARE_TURN_KEY_ID", ""), getattr(settings, "CLOUDFLARE_TURN_API_TOKEN", "")
    if not (key and token): return []
    servers = cache.get("cf-turn")
    if servers is None:
        req = urllib.request.Request(f"https://rtc.live.cloudflare.com/v1/turn/keys/{key}/credentials/generate-ice-servers",
                                     data=json.dumps({"ttl": 86400}).encode(), method="POST",
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=8) as r: servers = json.loads(r.read())["iceServers"]
            cache.set("cf-turn", servers, 6 * 3600)   # credentials live 24 hours; refresh well before that
        except Exception as e:
            log.error("Cloudflare TURN credentials failed: %s", e); return []
    return servers if isinstance(servers, list) else [servers]

def ice_servers():
    servers = list(STUN) + _cloudflare()
    urls = [u.strip() for u in getattr(settings, "TURN_URLS", "").split(",") if u.strip()]
    if urls:
        servers.append({"urls": urls, "username": settings.TURN_USERNAME, "credential": settings.TURN_CREDENTIAL})
    return servers

def has_relay():
    return len(ice_servers()) > len(STUN)
