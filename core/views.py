from datetime import date
from django.shortcuts import render
from .models import *

LOCATIONS = ["Dar es Salaam", "Arusha", "Mwanza", "Dodoma", "Zanzibar"]

def home(request):
    gold = Plan.objects.order_by("price").first()
    return render(request, "home.html", {
        "categories": ServiceCategory.objects.all()[:8],
        "matches": Member.objects.filter(featured=True)[:4],
        "events": Event.objects.filter(date__gte=date.today())[:3],
        "perks": PremiumPerk.objects.all(),
        "from_price": gold.price if gold else 0,
        "strip": FeatureStrip.objects.all(),
        "locations": LOCATIONS,
    })
