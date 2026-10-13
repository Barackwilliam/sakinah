"""Starter honeymoon destinations and packages (the client edits or replaces them from the dashboard)."""
from django.core.files import File
from .models import Destination, Package, PackagePhoto

DESTINATIONS = [  # name, country, kind, region, tagline, rating, reviews, days, nights, features, price, featured, image, description
    ("Zanzibar", "Tanzania", "beach", "tanzania", "White sandy beaches, turquoise waters and luxury resorts.", 4.8, 432, 5, 4,
     "bed|Hotel\nfood|Meals\nmap|Tours", 2_500_000, True, "zanzibar",
     "The Spice Island is made for newly-weds: powder-white beaches, warm turquoise water, historic Stone Town and sunsets you will remember for the rest of your lives."),
    ("Serengeti", "Tanzania", "safari", "tanzania", "Unforgettable safari experience and romantic wilderness.", 4.7, 321, 6, 5,
     "bed|Lodge\nfood|Meals\nsafari|Game Drives", 3_800_000, True, "serengeti",
     "Wake up to the sounds of the savannah, watch the Great Migration together and end each day with a private dinner under the African stars."),
    ("Maldives", "Maldives", "resort", "international", "World-class luxury and ultimate romantic escape.", 4.9, 310, 5, 4,
     "villa|Resort\nfood|All Meals\nwave|Water Activities", 7_800_000, True, "maldives",
     "Overwater villas, crystal lagoons and complete privacy: the Maldives is the classic once-in-a-lifetime honeymoon."),
    ("Seychelles", "Seychelles", "beach", "east-africa", "A paradise of pristine beaches and luxury resorts.", 4.8, 275, 6, 5,
     "villa|Resort\nfood|Meals\nmap|Island Tours", 6_500_000, True, "seychelles",
     "Granite boulders, quiet coves and lush forests make the Seychelles one of the most romantic island groups in the world."),
    ("Dubai", "UAE", "city", "international", "Modern luxury, stunning skyline and unique experiences.", 4.6, 289, 5, 4,
     "bed|Hotel\nfood|Meals\ncity|City Tours", 4_200_000, True, "dubai",
     "Five-star hotels, desert safaris, fine dining and the world's tallest tower: Dubai blends luxury and adventure, with halal food everywhere."),
    ("Ngorongoro", "Tanzania", "safari", "tanzania", "Breathtaking landscapes and unique wildlife.", 4.6, 210, 4, 3,
     "bed|Lodge\nfood|Meals\nsafari|Game Drives", 3_200_000, False, "ngorongoro",
     "Stay on the rim of the world's largest intact volcanic caldera and explore a crater full of lions, rhinos and flamingos."),
    ("Kilimanjaro", "Tanzania", "mountains", "tanzania", "Adventure, romance and stunning views.", 4.7, 180, 4, 3,
     "bed|Lodge\nfood|Meals\nhike|Hiking", 2_900_000, False, "kilimanjaro",
     "Cosy lodges, waterfalls and coffee farms at the foot of Africa's highest mountain, for couples who love fresh air and adventure."),
    ("Mafia Island", "Tanzania", "beach", "tanzania", "Secluded beaches and marine adventures.", 4.7, 198, 5, 4,
     "villa|Resort\nfood|Meals\ndive|Diving", 2_900_000, False, "mafia",
     "A peaceful marine park with whale sharks, coral gardens and empty beaches, far from the crowds."),
    ("Mauritius", "Mauritius", "resort", "east-africa", "Luxury resorts and breathtaking coastlines.", 4.8, 260, 6, 5,
     "villa|Resort\nfood|Meals\nmap|Island Tours", 5_800_000, False, "mauritius",
     "Lagoons, mountains and world-class resorts with spa treatments and private beach dinners for two."),
    ("Cape Town", "South Africa", "romantic", "international", "Stunning landscapes, wine tours and romantic getaways.", 4.7, 230, 6, 5,
     "bed|Hotel\nfood|Meals\nmap|Tours", 5_200_000, False, "capetown",
     "Table Mountain, scenic coastal drives and the Cape Winelands: a romantic city break with endless views."),
]

ZANZIBAR = [  # title, badge, tone, rating, reviews, days, nights, stay, stars, meals, extra, extra icon, price, type, image, flags
    ("Zanzibar Romantic Getaway", "Best Seller", "gold", 4.8, 432, 5, 4, "Luxury Resort", 5, "All Meals", "Airport Transfer", "car", 2_500_000, "beach", "romantic", "discount free"),
    ("Zanzibar Luxury Escape", "Luxury", "green", 4.9, 321, 7, 6, "5 Star Resort", 5, "All Meals", "Private Tour", "map", 4_800_000, "resort", "luxury", "free"),
    ("Zanzibar Beach Romance", "All Inclusive", "blue", 4.7, 275, 4, 3, "Beach Resort", 4, "All Meals", "Water Activities", "wave", 3_200_000, "all-inclusive", "beach_romance", "all"),
    ("Zanzibar Ultimate Honeymoon", "Honeymoon Special", "pink", 4.8, 198, 6, 5, "Luxury Resort", 5, "All Meals", "Candle Dinner", "heart", 5_500_000, "resort", "ultimate", "discount free all"),
    ("Tanzania Safari & Zanzibar Honeymoon", "Safari & Beach", "orange", 4.9, 310, 8, 7, "Safari Lodge", 5, "All Meals", "Flights Included", "plane", 7_800_000, "safari", "safari_beach", "all"),
    ("Zanzibar Private Villa Experience", "Private Villa", "purple", 4.8, 220, 5, 4, "Private Villa", 5, "All Meals", "Butler Service", "villa", 6_500_000, "resort", "villa", "free"),
    ("Zanzibar Adventure & Romance", "Romantic Adventure", "green", 4.7, 165, 6, 5, "Beach Resort", 4, "All Meals", "Snorkeling", "dive", 3_800_000, "beach", "adventure", "discount"),
    ("Zanzibar Short Honeymoon", "Budget Friendly", "navy", 4.6, 142, 3, 2, "Beach Hotel", 3, "Breakfast", "Island Tour", "map", 1_900_000, "beach", "short", ""),
]

OTHERS = [  # destination, title, badge, tone, rating, reviews, days, nights, stay, stars, meals, extra, icon, price, type, image, flags
    ("Serengeti", "Serengeti Romantic Safari", "Best Seller", "gold", 4.8, 214, 6, 5, "Safari Lodge", 5, "All Meals", "Game Drives", "safari", 3_800_000, "safari", "d_serengeti", "free"),
    ("Serengeti", "Serengeti Tented Camp Honeymoon", "Luxury", "green", 4.7, 107, 5, 4, "Luxury Tented Camp", 5, "All Meals", "Bush Dinner", "heart", 4_600_000, "safari", "p_safari_beach", "all"),
    ("Maldives", "Maldives Overwater Experience", "Luxury", "green", 4.9, 196, 5, 4, "Overwater Villa", 5, "All Meals", "Water Activities", "wave", 7_800_000, "resort", "d_maldives", "all"),
    ("Maldives", "Maldives All Inclusive Honeymoon", "All Inclusive", "blue", 4.8, 114, 7, 6, "Luxury Resort", 5, "All Meals", "Spa for Two", "heart", 9_900_000, "all-inclusive", "g_main", "all free"),
    ("Seychelles", "Seychelles Honeymoon", "Honeymoon Special", "pink", 4.8, 175, 6, 5, "Beach Resort", 5, "All Meals", "Island Tours", "map", 6_500_000, "beach", "d_seychelles", "discount"),
    ("Seychelles", "Seychelles Island Hopping", "Romantic Adventure", "green", 4.7, 100, 7, 6, "Boutique Hotels", 4, "Breakfast", "Snorkeling", "dive", 5_900_000, "beach", "p_adventure", ""),
    ("Dubai", "Dubai Honeymoon Escape", "Best Seller", "gold", 4.6, 189, 5, 4, "5 Star Hotel", 5, "Breakfast", "City Tours", "city", 4_200_000, "city", "d_dubai", "free"),
    ("Dubai", "Dubai Desert & City Romance", "Luxury", "green", 4.7, 100, 6, 5, "Luxury Hotel", 5, "All Meals", "Desert Safari", "safari", 5_400_000, "city", "p_beach_romance", "discount"),
    ("Ngorongoro", "Ngorongoro Crater Honeymoon", "Best Seller", "gold", 4.6, 210, 4, 3, "Crater Lodge", 5, "All Meals", "Game Drives", "safari", 3_200_000, "safari", "d_ngorongoro", "all"),
    ("Kilimanjaro", "Kilimanjaro Romance & Adventure", "Romantic Adventure", "green", 4.7, 180, 4, 3, "Mountain Lodge", 4, "All Meals", "Waterfall Hike", "hike", 2_900_000, "safari", "d_kilimanjaro", "discount"),
    ("Mafia Island", "Mafia Island Marine Romance", "Honeymoon Special", "pink", 4.7, 198, 5, 4, "Beach Resort", 4, "All Meals", "Diving", "dive", 2_900_000, "beach", "d_mafia", "free"),
    ("Mauritius", "Mauritius Luxury Honeymoon", "Luxury", "green", 4.8, 260, 6, 5, "Luxury Resort", 5, "All Meals", "Island Tours", "map", 5_800_000, "resort", "d_mauritius", "all"),
    ("Cape Town", "Cape Town Romance & Wine Tour", "Best Seller", "gold", 4.7, 230, 6, 5, "Boutique Hotel", 5, "Breakfast", "Scenic Tours", "map", 5_200_000, "city", "d_capetown", "discount"),
]

ROMANTIC_GETAWAY = dict(
    overview=("Indulge in a romantic escape to Zanzibar, where turquoise waters, white sandy beaches and luxury resorts create the perfect setting "
              "for your honeymoon. This package combines relaxation, adventure and unforgettable experiences designed for couples."),
    highlights="palm|Pristine Beaches\nheart|Romantic Dinners\ndive|Snorkeling & Marine Life\nboat|Sunset Cruise\ncamera|Stone Town Tour\ngift|Special Honeymoon Gifts",
    itinerary=("Day 1 - Karibu Zanzibar|Private airport pickup, welcome drinks and flowers in your suite, then a relaxed sunset dinner on the beach.\n"
               "Day 2 - Stone Town & Spice Tour|Walk the narrow streets of historic Stone Town, visit a spice farm and enjoy a Swahili lunch together.\n"
               "Day 3 - Ocean Adventure|Boat trip to Mnemba Atoll for snorkeling with turtles and dolphins, followed by a sunset dhow cruise.\n"
               "Day 4 - Spa & Candle-lit Dinner|A couple's spa massage in the morning, free afternoon at the beach and a private candle-lit dinner.\n"
               "Day 5 - Kwaheri|Breakfast in bed, last swim and private transfer to the airport with a honeymoon gift."),
    inclusions=("4 nights in an ocean-view suite at a luxury resort\nBreakfast, lunch and dinner (halal)\nReturn airport transfers\n"
                "Stone Town and spice tour with a guide\nMnemba Atoll snorkeling trip\nSunset dhow cruise\nOne couple's spa massage\n"
                "Private candle-lit beach dinner\nHoneymoon room decoration and gift"),
    exclusions="International and domestic flights (available on request)\nTravel insurance\nVisa fees\nPersonal expenses and tips",
    accommodation=("You stay in an ocean-view honeymoon suite with a king-size canopy bed, private terrace and outdoor shower. "
                   "The resort has an infinity pool, a quiet prayer room, halal restaurants and direct access to a white-sand beach."),
    activities="Snorkeling at Mnemba Atoll\nSunset dhow cruise\nStone Town walking tour\nSpice farm visit\nCouple's spa massage\nPrivate beach dinner",
    important_info=("Prices are per couple and depend on the travel dates\nA 30% deposit confirms the booking; the balance is due 21 days before travel\n"
                    "Free cancellation up to 30 days before arrival\nPlease bring a valid passport and your marriage certificate"),
)

def generic(dest, days, nights, stay, extra):
    """Readable default content for packages the client has not written in full yet."""
    days_text = [f"Day 1 - Arrival in {dest}|Private airport pickup, welcome drinks and check-in to your {stay.lower()}."]
    middle = [f"Explore {dest}|A guided tour of the best places in {dest}, with lunch together.",
              f"{extra}|A day planned around {extra.lower()}, with plenty of time to relax.",
              "Romance Day|Couple's spa treatment and a private candle-lit dinner.",
              "Free Day|Enjoy the resort at your own pace.",
              "Sunset Experience|An unforgettable sunset activity for two.",
              "Leisure|Relax, take photos and enjoy local food."]
    for i in range(2, days):
        t, d = middle[(i - 2) % len(middle)].split("|")
        days_text.append(f"Day {i} - {t}|{d}")
    days_text.append(f"Day {days} - Departure|Breakfast and private transfer to the airport.")
    return dict(
        overview=f"A carefully planned honeymoon in {dest} for {days} days and {nights} nights. Relax, explore and celebrate the start of your marriage with experiences made for couples.",
        highlights=f"heart|Romantic Dinners\nstar|{extra}\ncamera|Photo Moments\ngift|Honeymoon Gifts",
        itinerary="\n".join(days_text),
        inclusions=f"{nights} nights at a {stay.lower()}\nHalal meals as listed\nReturn airport transfers\n{extra}\nHoneymoon room decoration",
        exclusions="International flights (available on request)\nTravel insurance\nVisa fees\nPersonal expenses",
        accommodation=f"A romantic room at a {stay.lower()} chosen for couples, with a private bathroom and beautiful views.",
        activities=f"{extra}\nRomantic dinner for two\nGuided sightseeing",
        important_info="Prices are per couple and depend on the travel dates\nA 30% deposit confirms the booking\nBring a valid passport and your marriage certificate",
    )

ZANZIBAR_GALLERY = ["g_room", "g_dinner", "g_dive", "g_stone", "p_luxury", "p_beach_romance", "p_ultimate", "p_villa", "p_adventure", "p_short", "d_zanzibar"]
EXTRA_GALLERY = ["g_room", "g_dinner", "p_beach_romance"]

def seed_honeymoon(attach, folder):
    img = lambda n: folder / f"hm_{n}.jpg"
    dests = {}
    for i, (name, country, kind, region, tag, rating, reviews, days, nights, feats, price, featured, image, desc) in enumerate(DESTINATIONS):
        d, _ = Destination.objects.get_or_create(slug=name.lower().replace(" ", "-"), defaults=dict(
            name=name, country=country, kind=kind, region=region, tagline=tag, rating=rating, reviews=reviews, days=days, nights=nights,
            features=feats, from_price=price, featured=featured, order=i, description=desc))
        attach(d, "image", img(f"d_{image}")); dests[name] = d
    rows = [("Zanzibar", *r[:14], f"p_{r[14]}", r[15]) for r in ZANZIBAR] + list(OTHERS)
    for i, (dest, title, badge, tone, rating, reviews, days, nights, stay, stars, meals, extra, icon, price, ptype, image, flags) in enumerate(rows):
        slug = title.lower().replace(" & ", "-").replace(" ", "-")
        content = ROMANTIC_GETAWAY if title == "Zanzibar Romantic Getaway" else generic(dest, days, nights, stay, extra)
        location = "Arusha & Zanzibar, Tanzania" if "Safari & Zanzibar" in title else f"{dest}, {dests[dest].country}"
        p, created = Package.objects.get_or_create(slug=slug, defaults=dict(
            destination=dests[dest], title=title, location=location, package_type=ptype, badge=badge, badge_tone=tone, rating=rating, reviews=reviews,
            days=days, nights=nights, stay=stay, stars=stars, meals=meals, meals_detail="Breakfast only" if meals == "Breakfast" else "Breakfast, Lunch & Dinner",
            extra=extra, extra_icon=icon, price=price, discount="discount" in flags, free_addons="free" in flags, all_inclusive="all" in flags,
            featured=i < 4, order=i, flights="Included" if "Flights" in extra else "Available on request", **content))
        attach(p, "image", img("g_main" if title == "Zanzibar Romantic Getaway" else image))
        if created:
            for j, name in enumerate(ZANZIBAR_GALLERY if title == "Zanzibar Romantic Getaway" else EXTRA_GALLERY):
                ph = PackagePhoto(package=p, order=j)
                with open(img(name), "rb") as fh: ph.image.save(f"hm_{name}.jpg", File(fh), save=True)
