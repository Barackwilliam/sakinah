from datetime import date
from pathlib import Path
from django.core.files import File
from django.conf import settings
from django.core.management.base import BaseCommand
from core.models import *

class Command(BaseCommand):
    help = "Load initial Nusrah content (text only; upload images via /admin -> Supabase bucket)"
    def handle(self, *a, **k):
        SiteSetting.objects.get_or_create(pk=1)
        cats = [("Bridal Fashion","Dresses, hijab, suits\n& accessories"),("Beauty & Makeup","Bridal makeup, henna\n& beauty services"),
          ("Photography & Video","Capture your\nspecial moments"),("Decoration & Flowers","Stages, décor,\nflowers & design"),
          ("Catering","Wedding meals,\ncakes & refreshments"),("Wedding Venues","Halls, hotels & venues"),
          ("Wedding Transport","Bridal cars &\ntransportation"),("Invitations","Digital & printed\ninvitations")]
        for i,(n,b) in enumerate(cats):
            ServiceCategory.objects.get_or_create(slug=n.lower().replace(" & ","-").replace(" ","-"),
              defaults=dict(name=n,blurb=b.replace("\n"," "),order=i,button_label="View Venues" if n=="Wedding Venues" else "View Advert"))
        IMG = Path(settings.BASE_DIR) / "seed_images"
        for n,a,c,o,comp,g,f,img in [("Amina",28,"Dar es Salaam","Accountant",91,"F",1,"amina"),("Hassan",31,"Arusha","Engineer",88,"M",1,"hassan"),
                                 ("Zahra",26,"Mwanza","Teacher",85,"F",1,"zahra"),("Omar",30,"Dar es Salaam","Business Owner",87,"M",1,"omar"),
                                 ("Maryam",24,"Arusha","Nurse",86,"F",0,"maryam")]:
            m,_ = Member.objects.get_or_create(name=n,age=a,defaults=dict(city=c,occupation=o,compatibility=comp,gender=g,verified=True,featured=bool(f)))
            p = IMG / f"{img}.jpg"
            if not m.photo and p.exists():
                with open(p,"rb") as fh: m.photo.save(p.name, File(fh), save=True)
        for n,p in [("Free",0),("Basic",10000),("Silver",25000),("Gold",50000),("Tanzanite",100000)]:
            Plan.objects.get_or_create(name=n,defaults=dict(price=p,order=p))
        Plan.objects.filter(name="Free").delete()
        for i,t in enumerate(["See who likes you","Advanced matching","Unlimited messaging","Incognito mode","Voice & video calls","Priority support"]):
            PremiumPerk.objects.get_or_create(text=t,defaults=dict(order=i))
        for t,d,c,desc in [("Marriage Seminar",date(2026,12,15),"Dar es Salaam","Preparing for a Successful Marriage"),
            ("Singles & Marriage Meeting",date(2026,12,22),"Arusha","Meet verified members in person"),
            ("Nikah Preparation Workshop",date(2027,1,12),"Online Event","Guidance and counselling")]:
            Event.objects.get_or_create(title=t,defaults=dict(date=d,city=c,description=desc))
        for i,(t,x,ic) in enumerate([("Find a Match","Verified & genuine members","heart-f"),("Marriage Services","Trusted wedding vendors","ring"),
            ("Events & Workshops","Get guidance and meet people","cal"),("Articles & Advice","Relationship and marriage tips","book"),("Safe & Secure","Your privacy is our priority","shield")]):
            FeatureStrip.objects.get_or_create(title=t,defaults=dict(text=x,icon=ic,order=i))
        self.stdout.write("Seeded.")
