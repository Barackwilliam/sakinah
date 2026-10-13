"""Shared queries for the member area."""
from datetime import timedelta
from django.db.models import Count, Q
from django.utils import timezone
from core.models import Block, Like, Member, Message, Shortlist

def blocked_ids(user):
    return set(Block.objects.filter(user=user).values_list("member_id", flat=True))

def liked_me(member):
    """Users who liked this member, as Member rows (members without a login cannot like)."""
    if member is None: return Member.objects.none()
    return Member.objects.filter(user__likes__member=member).distinct()

def i_liked(user):
    return Member.objects.filter(likes__user=user).distinct()

def mutual(user, member):
    if member is None: return Member.objects.none()
    return i_liked(user).filter(user__likes__member=member).distinct()

def all_matches(user, member):
    ids = set(i_liked(user).values_list("pk", flat=True)) | set(liked_me(member).values_list("pk", flat=True))
    return Member.objects.filter(pk__in=ids)

def counts(user, member):
    """Sidebar and header badges for every member page: three small queries, done once per request."""
    if not hasattr(user, "_member_counts"): user._member_counts = _counts(user, member)
    return user._member_counts

def _counts(user, member):
    unread = Message.objects.filter(to__user=user, read=False).count()
    n_notes = user.notifications.filter(read=False).count()
    if member is None: return {"unread": unread, "new_likes": 0, "n_notes": n_notes, "n_matches": 0}
    since = member.likes_seen_at
    matched, new_likes = set(), 0
    # likes I gave and likes I received, in one query
    for liker, liked, liker_member, created in Like.objects.filter(Q(user=user) | Q(member=member)).values_list("user_id", "member_id", "user__member", "created"):
        if liker == user.id: matched.add(liked)
        if liked == member.pk and liker != user.id:
            if liker_member: matched.add(liker_member)
            if not since or created > since: new_likes += 1
    return {"unread": unread, "new_likes": new_likes, "n_notes": n_notes, "n_matches": len(matched)}

def photo_count(member):
    """Profile photo plus gallery photos, counted once per request."""
    if not hasattr(member, "_photo_count"): member._photo_count = member.photos.count()
    return member._photo_count

def period_counts(qs, field="created"):
    """{"all", "7", "month", "90"} counts for the period tabs, in one query."""
    now = timezone.now()
    since = {"7": now - timedelta(days=7), "month": now.replace(day=1, hour=0, minute=0, second=0, microsecond=0), "90": now - timedelta(days=90)}
    return qs.aggregate(n_all=Count("pk"), **{f"n_{k}": Count("pk", filter=Q(**{f"{field}__gte": v})) for k, v in since.items()})

COMPLETION = [  # (section, label, test)
    ("Basic Information", "name, age, city and occupation", lambda m: all([m.name, m.age, m.city, m.occupation])),
    ("Basic Information", "education", lambda m: bool(m.education)),
    ("Basic Information", "height", lambda m: bool(m.height_cm)),
    ("Basic Information", "languages", lambda m: bool(m.languages)),
    ("Photos", "profile photo", lambda m: bool(m.photo)),
    ("Photos", "at least 3 more photos", lambda m: photo_count(m) >= 3),
    ("About Me", "about me", lambda m: len(m.bio) >= 40),
    ("About Me", "interests", lambda m: bool(m.interests)),
    ("About Me", "religion & values", lambda m: bool(m.prayer or m.values)),
    ("About Me", "family background", lambda m: bool(m.father_status or m.family_type)),
    ("Partner Preferences", "preferred age", lambda m: bool(m.pref_age_min and m.pref_age_max)),
    ("Partner Preferences", "preferred location", lambda m: bool(m.pref_location)),
    ("Verification", "verified profile", lambda m: m.verified),
]

def completion(member):
    if member is None: return {"pct": 0, "sections": [], "missing": []}
    done = [(sec, label, bool(test(member))) for sec, label, test in COMPLETION]
    sections = []
    for sec in dict.fromkeys(s for s, _, _ in COMPLETION):
        items = [ok for s, _, ok in done if s == sec]
        sections.append({"name": sec, "done": all(items)})
    photos = (1 if member.photo else 0) + photo_count(member)
    for s in sections:
        if s["name"] == "Photos": s["name"] = f"Photos ({min(photos, 6)}/6)"
    return {"pct": round(100 * sum(ok for *_, ok in done) / len(done)), "sections": sections,
            "missing": [label for _, label, ok in done if not ok]}

def suggestions(user, member, limit=8):
    qs = Member.objects.exclude(pk=getattr(member, "pk", None)).exclude(pk__in=blocked_ids(user)).exclude(profile_visibility="hidden")
    qs = qs.filter(show_in_search=True, status="active")
    if member:
        qs = qs.filter(gender="M" if member.gender == "F" else "F", religion=member.religion).exclude(pk__in=i_liked(user).values("pk"))
        if member.pref_age_min: qs = qs.filter(age__gte=member.pref_age_min)
        if member.pref_age_max: qs = qs.filter(age__lte=member.pref_age_max)
    return qs.order_by("-verified", "-compatibility", "-joined")[:limit]

def period_filter(qs, field, key):
    now = timezone.now()
    days = {"7": 7, "week": 7, "30": 30, "month": 30, "90": 90}.get(key)
    if key == "month": return qs.filter(**{f"{field}__gte": now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)})
    return qs.filter(**{f"{field}__gte": now - timedelta(days=days)}) if days else qs
