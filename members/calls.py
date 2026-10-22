"""Voice and video calls: start, ring, answer, exchange connection details and hang up. See core/models_calls.py."""
import json
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from core.ice import ice_servers
from core.models import Block, Call, CallSignal, Member, Message, Notification

def call_permission(me, other):
    """(allowed, reason) for `me` calling `other`: a plan with call time left, and no block either way."""
    if other is None or not other.user_id or other.pk == me.pk: return False, "This member can't receive calls."
    if not me.is_active_member or not other.is_active_member: return False, "Calls are not available for this account."
    if Block.objects.filter(Q(user=me.user, member=other) | Q(user=other.user, member=me)).exists():
        return False, "You can't call this member."
    if me.allowance("daily_call_seconds") == 0: return False, "premium"
    if me.call_seconds_left == 0: return False, "spent"
    return True, ""

def call_cap(call):
    """Seconds this call may still run on the caller's daily allowance, or None when the plan is unlimited."""
    me = getattr(call.caller, "member", None)
    if me is None: return 0
    allowed = me.allowance("daily_call_seconds")
    if allowed < 0: return None
    return max(0, allowed - (me.used_today("daily_call_seconds") - call.seconds))

def finish(call, status):
    """Close a call and leave a line in the chat ("Missed video call", "Voice call · 2:31")."""
    if not call.live: return call
    call.status, call.ended_at = status, timezone.now()
    call.billed_seconds = call.seconds                       # what this call took off the caller's daily allowance
    call.save(update_fields=["status", "ended_at", "billed_seconds"])
    kind = call.get_kind_display().lower()
    text = {"ended": f"{kind.capitalize()} · {call.duration_text}", "declined": f"{kind.capitalize()} declined",
            "missed": f"Missed {kind}", "cancelled": f"Missed {kind}"}[status]
    callee = getattr(call.callee, "member", None)
    if callee:
        Message.objects.create(sender=call.caller, to=callee, body=text, kind="call", read=status == "ended")
        if status in ("missed", "cancelled"):
            caller = getattr(call.caller, "member", None)
            Notification.objects.create(user=call.callee, title=f"Missed {kind} from {caller.name if caller else call.caller}",
                                        link=reverse("m_messages_with", args=[caller.pk]) if caller else reverse("m_messages"))
    return call

def tidy(qs):
    """Turn calls nobody answered into missed calls."""
    for c in qs.filter(status="ringing"):
        if c.expired(): finish(c, "missed")

def my_call(request, pk):
    call = get_object_or_404(Call.objects.select_related("caller__member", "callee__member"), pk=pk)
    if request.user.pk not in (call.caller_id, call.callee_id): raise Http404
    return call

@login_required
@require_POST
def start(request, pk):
    me, other = getattr(request.user, "member", None), Member.objects.filter(pk=pk).select_related("user").first()
    kind = "video" if request.POST.get("kind") == "video" else "voice"
    if me is None: return JsonResponse({"ok": False, "error": "Complete your profile first."}, status=400)
    ok, reason = call_permission(me, other)
    if not ok:
        if reason == "premium":
            return JsonResponse({"ok": False, "premium": True, "url": reverse("m_membership"),
                                 "error": "Your plan does not include calls. Upgrade to call other members."}, status=403)
        if reason == "spent":
            return JsonResponse({"ok": False, "premium": True, "url": reverse("m_membership"),
                                 "error": "You have used today's call time. It comes back in 24 hours, or upgrade for more."}, status=403)
        return JsonResponse({"ok": False, "error": reason}, status=403)
    tidy(Call.objects.filter(Q(caller=other.user) | Q(callee=other.user) | Q(caller=request.user) | Q(callee=request.user)))
    if Call.objects.filter(Q(caller=other.user) | Q(callee=other.user), status__in=["ringing", "accepted"]).exists():
        return JsonResponse({"ok": False, "error": f"{other.first_name} is on another call. Try again in a few minutes."}, status=409)
    Call.objects.filter(Q(caller=request.user) | Q(callee=request.user), status__in=["ringing", "accepted"]).update(status="ended", ended_at=timezone.now())
    call = Call.objects.create(caller=request.user, callee=other.user, kind=kind)
    return JsonResponse({"ok": True, "id": call.pk, "url": reverse("m_call", args=[call.pk])})

@login_required
def incoming(request):
    """Polled every few seconds by every member page: is someone calling me right now?"""
    qs = Call.objects.filter(callee=request.user, status="ringing").select_related("caller__member")
    tidy(qs)
    call = qs.filter(status="ringing").first()
    if not call: return JsonResponse({"call": None})
    m = getattr(call.caller, "member", None)
    return JsonResponse({"call": {"id": call.pk, "kind": call.kind, "name": m.name if m else call.caller.get_username(),
                                  "photo": m.photo.url if m and m.photo else "", "url": reverse("m_call", args=[call.pk]) + "?answer=1",
                                  "decline": reverse("m_call_end", args=[call.pk])}})

@login_required
def screen(request, pk):
    call = my_call(request, pk)
    tidy(Call.objects.filter(pk=call.pk)); call.refresh_from_db()
    me_caller = call.caller_id == request.user.pk
    other = getattr(call.callee if me_caller else call.caller, "member", None)
    if not call.live:
        return redirect(reverse("m_messages_with", args=[other.pk]) if other else reverse("m_messages"))
    return render(request, "members/call.html", {"call": call, "other": other, "is_caller": me_caller, "answer": request.GET.get("answer") == "1",
        "ice": ice_servers(), "cap": call_cap(call) or 0,
        "back": reverse("m_messages_with", args=[other.pk]) if other else reverse("m_messages")})

@login_required
@require_POST
def answer(request, pk):
    call = my_call(request, pk)
    if call.callee_id != request.user.pk or call.status != "ringing" or call.expired():
        return JsonResponse({"ok": False, "status": call.status}, status=409)
    call.status, call.answered_at = "accepted", timezone.now()
    call.save(update_fields=["status", "answered_at"])
    return JsonResponse({"ok": True})

@login_required
@require_POST
def end(request, pk):
    """Hang up, decline or cancel, depending on who presses it and when."""
    call = my_call(request, pk)
    if call.status == "ringing":
        finish(call, "declined" if call.callee_id == request.user.pk else ("missed" if call.expired() else "cancelled"))
    elif call.status == "accepted":
        finish(call, "ended")
    return JsonResponse({"ok": True, "status": call.status})

@login_required
def state(request, pk):
    """Call status plus the other browser's connection messages newer than ?after=."""
    call = my_call(request, pk)
    if call.expired(): finish(call, "missed")
    cap = call_cap(call)
    if call.status == "accepted" and cap is not None and call.seconds >= cap: finish(call, "ended")
    after = int(request.GET.get("after") or 0) if (request.GET.get("after") or "0").isdigit() else 0
    sig = call.signals.filter(pk__gt=after).exclude(sender=request.user).values("pk", "kind", "data")[:100]
    return JsonResponse({"status": call.status, "seconds": call.seconds, "cap": cap or 0, "signals": [{"id": s["pk"], "kind": s["kind"], "data": s["data"]} for s in sig]})

@login_required
@require_POST
def signal(request, pk):
    call = my_call(request, pk)
    if not call.live: return JsonResponse({"ok": False, "status": call.status}, status=409)
    try: items = json.loads(request.body or b"[]")
    except ValueError: return JsonResponse({"ok": False}, status=400)
    if isinstance(items, dict): items = [items]
    rows = [CallSignal(call=call, sender=request.user, kind=i.get("kind"), data=json.dumps(i.get("data"))[:20000])
            for i in items[:50] if isinstance(i, dict) and i.get("kind") in ("offer", "answer", "ice")]
    CallSignal.objects.bulk_create(rows)
    return JsonResponse({"ok": True})
