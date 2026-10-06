from datetime import date
from pathlib import Path
from django.core.files import File
from django.conf import settings
from django.core.management.base import BaseCommand
from core.models import *

class Command(BaseCommand):
    help = "Load initial Sakinah content and placeholder images (replace images any time via /admin)"
    def handle(self, *a, **k):
        IMG = Path(settings.BASE_DIR) / "seed_images"
        def attach(obj, field, path):
            if not getattr(obj, field) and path.exists():
                with open(path, "rb") as fh: getattr(obj, field).save(path.name, File(fh), save=True)
        site, _ = SiteSetting.objects.get_or_create(pk=1)
        for field, name in [("hero_image", "hero"), ("premium_image", "premium"), ("advert_image", "advert")]:
            attach(site, field, IMG / "site" / f"{name}.jpg")
        cats = [("Bridal Fashion","Dresses, hijab, suits\n& accessories"),("Beauty & Makeup","Bridal makeup, henna\n& beauty services"),
          ("Photography & Video","Capture your\nspecial moments"),("Decoration & Flowers","Stages, décor,\nflowers & design"),
          ("Catering","Wedding meals,\ncakes & refreshments"),("Wedding Venues","Halls, hotels & venues"),
          ("Wedding Transport","Bridal cars &\ntransportation"),("Invitations","Digital & printed\ninvitations")]
        for i,(n,b) in enumerate(cats):
            ServiceCategory.objects.get_or_create(slug=n.lower().replace(" & ","-").replace(" ","-"),
              defaults=dict(name=n,blurb=b.replace("\n"," "),order=i,button_label="View Venues" if n=="Wedding Venues" else "View Advert"))
        for c in ServiceCategory.objects.all(): attach(c, "image", IMG / "site" / f"svc_{c.slug}.jpg")
        people = [  # name, age, city, occupation, compat, gender, featured, image, religion, education, bio
            ("Amina",28,"Dar es Salaam","Accountant",91,"F",1,"amina","Islam","Shahada ya Uhasibu","Ninathamini imani, familia na heshima. Natafuta mume mcha Mungu kwa ajili ya ndoa ya kudumu."),
            ("Hassan",31,"Arusha","Engineer",88,"M",1,"hassan","Islam","Shahada","Ninapenda dini yangu, ninathamini familia, na ninatafuta mwenza wa maisha kwa ajili ya ndoa ya kudumu."),
            ("Zahra",26,"Mwanza","Teacher",85,"F",1,"zahra","Islam","Stashahada ya Ualimu","Mwalimu mpenda watoto na amani. Natafuta mwenza mwenye maadili ya Kiislamu."),
            ("Omar",30,"Dar es Salaam","Business Owner",87,"M",1,"omar","Islam","Shahada","Ninaheshimu dini, naweza kushirikiana, na ninatamani kupata mwenza wa maisha kwa ajili ya ndoa ya kudumu."),
            ("Maryam",24,"Arusha","Nurse",86,"F",0,"maryam","Islam","Stashahada ya Uuguzi","Ninapenda kusaidia watu. Natafuta mume mwenye upendo na heshima."),
            ("Salim",52,"Dodoma","Mfanyabiashara",84,"M",0,"salim","Islam","Shahada ya Uzamili","Ninaamini familia ni msingi wa maisha. Ninathamini maadili, heshima, na malezi mema. Ninataka mwenza wa maisha kwa ajili ya ndoa ya kudumu."),
            ("Daniel",32,"Arusha","Mchungaji",86,"M",0,"daniel","Christian","Shahada ya Theolojia","Ninampenda Mungu, na ninaamini katika familia. Ninatafuta mwenza wa maisha kwa ajili ya ndoa ya kudumu."),
            ("Abdullah",38,"Dar es Salaam","Mtaalamu wa TEHAMA",89,"M",0,"abdullah","Islam","Shahada ya Uzamili","Ninaamini katika familia yenye maadili ya Kiislamu. Napenda uaminifu, heshima na mawasiliano mazuri. Ninatafuta mwenza wa maisha kwa ajili ya ndoa ya kudumu."),
            ("Neema",27,"Mwanza","Muuguzi",83,"F",0,"church_woman","Christian","Stashahada ya Uuguzi","Ninamtumikia Mungu na ninapenda familia. Natafuta mume mwenye imani na upendo wa dhati."),
            ("Grace",29,"Dar es Salaam","Afisa Masoko",82,"F",0,"woman_pink","Christian","Shahada ya Biashara","Mchangamfu, mwenye bidii na mpenda familia. Natafuta mwenza wa maisha mwenye hofu ya Mungu."),
        ]
        for n,a,c,o,comp,g,f,img,rel,edu,bio in people:
            m,_ = Member.objects.get_or_create(name=n,age=a,defaults=dict(city=c,occupation=o,compatibility=comp,gender=g,verified=True,featured=bool(f),religion=rel))
            blank = [k for k in ("education", "bio") if not getattr(m, k)]
            for k in blank: setattr(m, k, {"education": edu, "bio": bio}[k])
            if blank: m.save(update_fields=blank)
            attach(m, "photo", IMG / f"{img}.jpg")
        for n,p in [("Free",0),("Basic",10000),("Silver",25000),("Gold",50000),("Tanzanite",100000)]:
            Plan.objects.get_or_create(name=n,defaults=dict(price=p,order=p))
        Plan.objects.filter(name="Free").delete()
        for i,t in enumerate(["See who likes you","Advanced matching","Unlimited messaging","Incognito mode","Voice & video calls","Priority support"]):
            PremiumPerk.objects.get_or_create(text=t,defaults=dict(order=i))
        for i,(t,d,c,desc) in enumerate([("Marriage Seminar",date(2026,12,15),"Dar es Salaam","Preparing for a Successful Marriage"),
            ("Singles & Marriage Meeting",date(2026,12,22),"Arusha","Meet verified members in person"),
            ("Nikah Preparation Workshop",date(2027,1,12),"Online Event","Guidance and counselling")]):
            e,_ = Event.objects.get_or_create(title=t,defaults=dict(date=d,city=c,description=desc))
            attach(e, "image", IMG / "site" / f"event{i+1}.jpg")
        for i,(t,x,ic) in enumerate([("Find a Match","Verified & genuine members","heart-f"),("Marriage Services","Trusted wedding vendors","ring"),
            ("Events & Workshops","Get guidance and meet people","cal-g"),("Articles & Advice","Relationship and marriage tips","book"),("Safe & Secure","Your privacy is our priority","shield-c")]):
            FeatureStrip.objects.get_or_create(title=t,defaults=dict(text=x,icon=ic,order=i))
        self.stdout.write("Seeded.")
