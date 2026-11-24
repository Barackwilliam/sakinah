"""{% banner "home" %}: one live banner for that place, taking turns at random; the view is counted."""
from django import template
from django.db.models import F
from ..models import BannerOrder

register = template.Library()


@register.inclusion_tag("partials/banner.html")
def banner(place, invite=False):
    b = BannerOrder.objects.live().filter(slot__place=place, slot__active=True).select_related("slot").order_by("?").first()
    if b is not None: BannerOrder.objects.filter(pk=b.pk).update(views=F("views") + 1)
    return {"b": b, "place": place, "invite": invite}
