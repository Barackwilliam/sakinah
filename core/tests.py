from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from datetime import date, timedelta
from .models import *

class FlowTests(TestCase):
    def setUp(self):
        self.amina = Member.objects.create(name="Amina", age=28, gender="F", city="Arusha", occupation="Accountant", verified=True)
        self.omar = Member.objects.create(name="Omar", age=40, gender="M", city="Dar es Salaam", occupation="Engineer")

    def signup(self, **kw):
        data = dict(username="juma", name="Juma Ali", email="juma@example.com", gender="M", age=30, city="Arusha", religion="Islam",
                    occupation="Teacher", password1="S3cure-pass-123", password2="S3cure-pass-123", **kw)
        return self.client.post(reverse("signup"), data)

    def test_pages_load(self):
        for name in ["home", "matches", "events", "services", "premium", "login", "signup"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        url = reverse("member", args=[self.amina.pk])
        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")

    def test_signup_creates_member_and_logs_in(self):
        r = self.signup()
        self.assertRedirects(r, reverse("m_profile_edit"))
        self.assertEqual(self.client.get(reverse("signup")).status_code, 302)
        m = Member.objects.get(user__username="juma")
        self.assertEqual((m.name, m.gender, m.city), ("Juma Ali", "M", "Arusha"))
        self.assertContains(self.client.get(reverse("home")), "Logout")

    def test_duplicate_email_rejected(self):
        User.objects.create_user("x", "juma@example.com", "pw")
        self.assertContains(self.signup(), "already exists")

    def test_matches_filters(self):
        r = self.client.get(reverse("matches"), {"seek": "F"})
        self.assertContains(r, "Amina"); self.assertNotContains(r, "Omar")
        r = self.client.get(reverse("matches"), {"age": "20-35"})
        self.assertContains(r, "Amina"); self.assertNotContains(r, "Omar")
        r = self.client.get(reverse("matches"), {"verified": "1", "city": "Dar es Salaam"})
        self.assertContains(r, "0 members found")

    def test_logged_in_man_sees_women_and_not_himself(self):
        self.signup()
        r = self.client.get(reverse("matches"))
        self.assertContains(r, "Amina"); self.assertNotContains(r, "Omar"); self.assertNotContains(r, "Juma Ali")

    def test_like_toggle(self):
        url = reverse("like", args=[self.amina.pk])
        self.assertRedirects(self.client.post(url), f"{reverse('login')}?next={url}")
        self.signup()
        self.client.post(url, {"next": "/matches/"})
        self.assertTrue(Like.objects.filter(member=self.amina).exists())
        self.assertContains(self.client.get(reverse("my_likes")), "Amina")
        self.client.post(url)
        self.assertFalse(Like.objects.exists())

    def test_like_rejects_external_next(self):
        self.signup()
        r = self.client.post(reverse("like", args=[self.amina.pk]), {"next": "https://evil.example.com/"})
        self.assertRedirects(r, reverse("member", args=[self.amina.pk]))

    def test_cannot_like_self(self):
        self.signup()
        me = Member.objects.get(user__username="juma")
        self.client.post(reverse("like", args=[me.pk]))
        self.assertFalse(Like.objects.exists())

    def test_profile_edit(self):
        self.signup()
        self.assertRedirects(self.client.get(reverse("profile_edit")), reverse("m_profile_edit"))
        r = self.client.post(reverse("m_profile_edit"), dict(name="Juma A.", age=31, gender="M", city="Mwanza", occupation="Teacher",
                                                             religion="Islam", practice="practising", marital_status="single", origin="Mtanzania", bio="Hello"))
        me = Member.objects.get(user__username="juma")
        self.assertRedirects(r, reverse("m_profile"))
        self.assertEqual((me.city, me.bio), ("Mwanza", "Hello"))

    def test_logout(self):
        self.signup()
        self.assertRedirects(self.client.post(reverse("logout")), reverse("home"))
        self.assertContains(self.client.get(reverse("home")), "Join Free")

    def test_anonymous_card_buttons_open_auth_modal(self):
        r = self.client.get(reverse("matches"))
        self.assertContains(r, 'id="amodal"')
        self.assertContains(r, f'data-auth="{reverse("thread", args=[self.amina.pk])}"')
        self.assertContains(r, "Imethibitishwa")
        self.signup()
        r = self.client.get(reverse("matches"), {"seek": "F"})
        self.assertNotContains(r, 'id="amodal"'); self.assertNotContains(r, "data-auth=")

    def test_signup_returns_to_next(self):
        url = reverse("thread", args=[self.amina.pk])
        self.assertRedirects(self.signup(next=url), url)
        self.assertRedirects(self.signup_external(), reverse("m_profile_edit"))

    def signup_external(self):
        self.client.logout()
        return self.client.post(reverse("signup"), dict(username="ali", name="Ali", email="ali@example.com", gender="M", age=33,
            city="Arusha", religion="Islam", occupation="Driver", password1="S3cure-pass-123", password2="S3cure-pass-123",
            next="https://evil.example.com/"))

    def test_messaging_between_members(self):
        self.signup()
        juma = Member.objects.get(user__username="juma")
        amina_user = User.objects.create_user("amina", "a@example.com", "S3cure-pass-123")
        self.amina.user = amina_user; self.amina.save()
        plan = Plan.objects.create(name="Chat test", price=5000, daily_messages=-1)   # messaging needs a plan that allows it
        Member.objects.filter(pk__in=[juma.pk, self.amina.pk]).update(plan=plan, premium_until=date.today() + timedelta(days=30))
        self.client.post(reverse("thread", args=[self.amina.pk]), {"body": "Assalaam alaikum"})
        self.assertEqual(Message.objects.get().to, self.amina)
        self.client.force_login(amina_user)
        self.assertContains(self.client.get(reverse("inbox")), "Juma Ali")
        r = self.client.get(reverse("thread", args=[juma.pk]))
        self.assertContains(r, "Assalaam alaikum")
        self.assertTrue(Message.objects.get().read)
        self.client.post(reverse("thread", args=[juma.pk]), {"body": "Wa alaikum salaam"})
        self.assertEqual(Message.objects.filter(to=juma).count(), 1)

    def test_whatsapp_only_when_opted_in(self):
        self.amina.phone = "+255 712 000 111"; self.amina.save()
        self.signup()
        self.assertNotContains(self.client.get(reverse("member", args=[self.amina.pk])), "wa.me")
        self.amina.whatsapp_ok = True; self.amina.save()
        self.assertContains(self.client.get(reverse("member", args=[self.amina.pk])), "https://wa.me/255712000111")

    def test_swahili_labels(self):
        self.assertEqual((self.amina.seeking, self.amina.marital), ("Mume wa Ndoa", "Hajaolewa"))
        self.assertEqual((self.omar.seeking, self.omar.marital), ("Mke wa Ndoa", "Hajaoa"))
        self.assertIn("Kiislamu", self.omar.goal_text)

    def test_login_with_email_or_username(self):
        User.objects.create_user("zuhura", "Zuhura@Example.com", "S3cure-pass-123")
        for name in ["zuhura", "zuhura@example.com"]:
            self.assertRedirects(self.client.post(reverse("login"), {"username": name, "password": "S3cure-pass-123"}), reverse("m_dashboard"))
            self.client.logout()
        r = self.client.post(reverse("login"), {"username": "zuhura@example.com", "password": "wrong"})
        self.assertEqual(r.status_code, 200)

    def test_login_page_uses_site_settings(self):
        r = self.client.get(reverse("login"))
        self.assertContains(r, "Sakinah")
        self.assertContains(r, "Welcome Back")
        self.assertContains(r, "Admin Login")


class SiteSectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("juma", "juma@example.com", "S3cure-pass-123")
        self.me = Member.objects.create(user=self.user, name="Juma", age=30, gender="M", city="Arusha", occupation="Teacher")
        self.zahra = Member.objects.create(name="Zahra", age=26, gender="F", city="Dar es Salaam", occupation="Teacher", prayer="Regularly")
        self.amina = Member.objects.create(name="Amina", age=28, gender="F", city="Arusha", occupation="Nurse")
        venues = ServiceCategory.objects.create(name="Wedding Venues", slug="wedding-venues", blurb="Halls")
        vendor = Vendor.objects.create(name="Al-Noor Events", slug="al-noor", city="Dar es Salaam", why_choose="Trusted\nHalal")
        self.ad = Advert.objects.create(category=venues, vendor=vendor, title="Al-Noor Wedding Hall", slug="al-noor-hall", city="Dar es Salaam",
            price=1500000, includes="Chairs\nSound", highlights="people|Up to 300 Guests")
        Advert.objects.create(category=venues, vendor=vendor, title="Baraka Gardens", slug="baraka", city="Dar es Salaam", price=1200000)
        cat = ArticleCategory.objects.create(name="Relationships", slug="relationships")
        self.article = Article.objects.create(title="Talk Kindly", slug="talk-kindly", category=cat, excerpt="Short", body="Long text", tags="Trust, Nikah")
        self.event = Event.objects.create(title="Nikah Workshop", date=date.today() + timedelta(days=5), city="Arusha")
        Event.objects.create(title="Old Seminar", date=date.today() - timedelta(days=5), city="Arusha")

    def test_public_pages(self):
        for url in [reverse("services"), reverse("advert", args=["al-noor-hall"]), reverse("articles"), self.article.get_absolute_url(),
                    reverse("events"), reverse("premium")]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_advert_page_and_views(self):
        r = self.client.get(reverse("advert", args=["al-noor-hall"]))
        self.assertContains(r, "Up to 300 Guests"); self.assertContains(r, "Baraka Gardens"); self.assertContains(r, "Trusted")
        self.ad.refresh_from_db(); self.assertEqual(self.ad.views, 1)
        r = self.client.get(reverse("services"), {"cat": "wedding-venues", "q": "baraka"})
        self.assertContains(r, "Baraka Gardens"); self.assertNotContains(r, "Al-Noor Wedding Hall</a>")

    def test_inquiry_works_without_login(self):
        self.client.post(reverse("inquire", args=["al-noor-hall"]), {"kind": "availability", "name": "Asha", "phone": "0712000111"})
        self.assertEqual(Inquiry.objects.get().kind, "availability")
        self.client.post(reverse("inquire", args=["al-noor-hall"]), {"kind": "inquiry", "name": "", "phone": ""})
        self.assertEqual(Inquiry.objects.count(), 1)

    def test_wishlist_and_review_need_login(self):
        url = reverse("wishlist", args=["al-noor-hall"])
        self.assertRedirects(self.client.post(url), f"{reverse('login')}?next={url}")
        self.client.force_login(self.user)
        self.client.post(url); self.assertTrue(Wishlist.objects.exists())
        self.client.post(url); self.assertFalse(Wishlist.objects.exists())
        self.client.post(reverse("review", args=["al-noor-hall"]), {"rating": 5, "comment": "Great"})
        self.client.post(reverse("review", args=["al-noor-hall"]), {"rating": 1, "comment": "Again"})
        self.assertEqual(AdvertReview.objects.get().rating, 5)
        self.assertContains(self.client.get(reverse("advert", args=["al-noor-hall"])), "5.0")

    def test_profile_prev_next_shortlist_report(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse("member", args=[self.zahra.pk]))
        self.assertContains(r, "Regularly"); self.assertContains(r, "Her Preferences")
        self.assertTrue(r.context["prev_id"] or r.context["next_id"])
        self.client.post(reverse("shortlist", args=[self.zahra.pk]))
        self.assertTrue(Shortlist.objects.filter(member=self.zahra).exists())
        self.assertContains(self.client.get(reverse("my_likes")), "Zahra")
        self.client.post(reverse("report", args=[self.zahra.pk]), {"reason": "fake", "details": "x"})
        self.assertEqual(Report.objects.get().member, self.zahra)

    def test_articles_filter_and_comments(self):
        self.assertContains(self.client.get(reverse("articles"), {"tag": "Trust"}), "Talk Kindly")
        self.assertNotContains(self.client.get(reverse("articles"), {"q": "nothing-like-this"}), "Talk Kindly</a>")
        url = self.article.get_absolute_url()
        self.assertRedirects(self.client.post(url, {"body": "Nice"}), f"{reverse('login')}?next={url}")
        self.client.force_login(self.user)
        self.client.post(url, {"body": "Nice"})
        self.assertEqual(ArticleComment.objects.get().body, "Nice")

    def test_events_upcoming_and_registration(self):
        r = self.client.get(reverse("events"))
        self.assertContains(r, "Nikah Workshop"); self.assertNotContains(r, "Old Seminar")
        self.assertContains(self.client.get(reverse("events"), {"when": "past"}), "Old Seminar")
        self.client.force_login(self.user)
        url = reverse("event_register", args=[self.event.pk])
        self.client.post(url); self.assertEqual(self.event.registrations.count(), 1)
        self.assertContains(self.client.get(reverse("events")), "Registered")
        self.client.post(url); self.assertEqual(self.event.registrations.count(), 0)

    def test_plan_features(self):
        p = Plan.objects.create(name="Gold", price=50000, features="Priority support\n-Incognito mode", popular=True,
                                daily_messages=-1, daily_call_seconds=300)
        self.assertEqual(p.feature_list, [(True, "Start as many chats as you like"), (True, "5 minutes of calls a day"),
                                          (True, "Priority support"), (False, "Incognito mode")])
        r = self.client.get(reverse("premium"))
        self.assertContains(r, "Most Popular"); self.assertContains(r, "Incognito mode")


class SeedTests(TestCase):
    def test_every_seeded_member_can_be_reached(self):
        """A member with no account of their own cannot be called, so the seed gives everyone one."""
        from django.core.management import call_command
        call_command("seed", verbosity=0)
        self.assertFalse(Member.objects.filter(user__isnull=True).exists())
        self.assertFalse(any(m.user.has_usable_password() for m in Member.objects.all()))   # not a way into the site

    def test_seed_runs_twice_and_fits_postgres_smallint(self):
        """SQLite ignores column sizes; PostgreSQL rejects values above 32767 in small integer fields."""
        from django.apps import apps
        from django.core.management import call_command
        from django.db import models as dm
        from io import StringIO
        call_command("seed", stdout=StringIO()); call_command("seed", stdout=StringIO())
        for model in apps.get_app_config("core").get_models():
            for f in model._meta.fields:
                if isinstance(f, (dm.PositiveSmallIntegerField, dm.SmallIntegerField)):
                    top = model.objects.aggregate(m=dm.Max(f.name))["m"] or 0
                    self.assertLessEqual(top, 32767, f"{model.__name__}.{f.name}")
        self.assertEqual(Plan.objects.count(), 5)


class UploadShrinkTests(TestCase):
    def test_large_photos_are_resized_and_small_ones_kept(self):
        import tempfile
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        m = Member.objects.create(name="Amina", age=28, gender="F", city="Arusha")
        big = BytesIO(); Image.effect_noise((3000, 2000), 60).convert("RGB").save(big, "JPEG", quality=95)
        small = BytesIO(); Image.new("RGBA", (50, 50), (0, 0, 0, 0)).save(small, "PNG")   # tiny icons are stored as they are
        with tempfile.TemporaryDirectory() as tmp, override_settings(MEDIA_ROOT=tmp):
            p = MemberPhoto.objects.create(member=m, image=SimpleUploadedFile("phone.jpeg", big.getvalue(), "image/jpeg"))
            self.assertLess(p.image.size, big.tell())
            self.assertEqual(max(Image.open(p.image.path).size), 1600)
            q = MemberPhoto.objects.create(member=m, image=SimpleUploadedFile("logo.png", small.getvalue(), "image/png"))
            self.assertEqual(q.image.size, small.tell())

    def test_every_picture_gets_the_watermark_once(self):
        import tempfile
        from io import BytesIO
        from PIL import Image
        from django.core.files.base import ContentFile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.core.management import call_command
        from django.test import override_settings
        from core.images import MARK
        photo = BytesIO(); Image.new("RGB", (800, 600), (40, 90, 160)).save(photo, "JPEG")
        with tempfile.TemporaryDirectory() as tmp, override_settings(MEDIA_ROOT=tmp, WATERMARK_TEXT="sakinah.co.tz"):
            p = MemberPhoto.objects.create(member=Member.objects.create(name="Amina", age=28, gender="F", city="Arusha"),
                                           image=SimpleUploadedFile("me.jpg", photo.getvalue(), "image/jpeg"))
            img = Image.open(p.image.path)
            self.assertIn(MARK.encode(), img.info.get("comment", b""))
            self.assertNotEqual(img.convert("RGB").getpixel((400, 372)), (40, 90, 160))   # letters drawn below the centre
            before = open(p.image.path, "rb").read()
            from io import StringIO; call_command("watermark_images", stdout=StringIO())
            self.assertEqual(open(p.image.path, "rb").read(), before)   # never stamped twice
            site = SiteSetting.load(); site.logo.save("logo.jpg", ContentFile(photo.getvalue()), save=False)
            self.assertNotIn(MARK.encode(), Image.open(site.logo.path).info.get("comment", b""))   # the logo stays clean
        with tempfile.TemporaryDirectory() as tmp, override_settings(MEDIA_ROOT=tmp, WATERMARK_TEXT=""):
            q = MemberPhoto.objects.create(member=p.member, image=SimpleUploadedFile("plain.jpg", photo.getvalue(), "image/jpeg"))
            self.assertEqual(q.image.size, len(photo.getvalue()))   # switched off: stored exactly as uploaded


class HoneymoonTests(TestCase):
    def setUp(self):
        from core.models import Destination, Package
        self.zanzibar = Destination.objects.create(name="Zanzibar", slug="zanzibar", country="Tanzania", kind="beach", region="tanzania",
                                                   tagline="White sand", from_price=2_500_000, featured=True)
        self.dubai = Destination.objects.create(name="Dubai", slug="dubai", country="UAE", kind="city", region="international", tagline="Skyline",
                                                from_price=4_200_000, days=8)
        self.pkg = Package.objects.create(destination=self.zanzibar, title="Zanzibar Romantic Getaway", slug="zanzibar-romantic-getaway", location="Zanzibar, Tanzania",
                                          price=2_500_000, badge="Best Seller", itinerary="Day 1 - Arrival|Pickup", inclusions="Hotel", discount=True)
        self.cheap = Package.objects.create(destination=self.zanzibar, title="Short Honeymoon", slug="short", location="Zanzibar", price=1_900_000, days=3, nights=2, stars=3)

    def test_pages_and_filters(self):
        self.assertContains(self.client.get(reverse("home")), "Honeymoon")
        r = self.client.get(reverse("hm_destinations"))
        self.assertContains(r, "Zanzibar"); self.assertContains(r, "Dubai")
        r = self.client.get(reverse("hm_destinations"), {"cat": "tanzania"})
        self.assertContains(r, "White sand"); self.assertNotContains(r, "Skyline")
        r = self.client.get(reverse("hm_destinations"), {"dur": "8-10", "sort": "-price", "view": "list", "min": "abc"})
        self.assertContains(r, "Dubai"); self.assertNotContains(r, "White sand")
        r = self.client.get(reverse("hm_destination", args=["zanzibar"]), {"stars": "3"})
        self.assertContains(r, "Short Honeymoon"); self.assertNotContains(r, "Romantic Getaway</a>")
        r = self.client.get(reverse("hm_packages"), {"offer": "discount"})
        self.assertContains(r, "Zanzibar Romantic Getaway"); self.assertNotContains(r, "Short Honeymoon</a>")
        r = self.client.get(reverse("hm_package", args=[self.pkg.slug]))
        self.assertContains(r, "Book This Package"); self.assertContains(r, "Day 1 - Arrival"); self.assertContains(r, "Short Honeymoon")
        self.pkg.active = False; self.pkg.save()
        self.assertEqual(self.client.get(reverse("hm_package", args=[self.pkg.slug])).status_code, 404)
        self.assertEqual(self.client.get(reverse("hm_destination", args=["nowhere"])).status_code, 404)

    def test_booking_request(self):
        from core.models import Booking
        url = reverse("hm_book", args=[self.pkg.slug])
        self.client.post(url, {"travel_date": "2001-01-01", "couples": 1, "name": "Asha", "phone": "0712"})
        self.assertFalse(Booking.objects.exists())
        user = User.objects.create_user("asha")
        self.client.force_login(user)
        r = self.client.post(url, {"travel_date": (date.today() + timedelta(days=60)).isoformat(), "couples": 2, "name": "Asha", "phone": "0712000000"})
        self.assertRedirects(r, self.pkg.get_absolute_url())
        b = Booking.objects.get()
        self.assertEqual((b.user, b.status, b.total), (user, "new", 5_000_000))
        self.assertTrue(Notification.objects.filter(user=user, title__contains="Booking request").exists())

    def test_save_and_review_need_login(self):
        from core.models import HoneymoonSave, PackageReview
        save = reverse("hm_save")
        self.assertEqual(self.client.post(save, {"kind": "package", "pk": self.pkg.pk}).status_code, 302)
        self.assertFalse(HoneymoonSave.objects.exists())
        self.client.force_login(User.objects.create_user("omar"))
        self.client.post(save, {"kind": "package", "pk": self.pkg.pk}); self.client.post(save, {"kind": "destination", "pk": self.dubai.pk})
        self.assertEqual(HoneymoonSave.objects.count(), 2)
        self.client.post(save, {"kind": "package", "pk": self.pkg.pk})
        self.assertEqual(HoneymoonSave.objects.count(), 1)
        self.assertEqual(self.client.post(save, {"kind": "member", "pk": "1"}).status_code, 302)
        review = reverse("hm_review", args=[self.pkg.slug])
        self.client.post(review, {"rating": 5, "comment": "Beautiful"}); self.client.post(review, {"rating": 1})
        self.assertEqual(PackageReview.objects.get().rating, 5)

    def test_dashboard_manages_honeymoon(self):
        from django.contrib.auth.models import Group
        from core.models import Booking
        staff = User.objects.create_user("boss", is_staff=True); staff.groups.add(Group.objects.get_or_create(name="Super Admins")[0])
        self.client.force_login(staff)
        b = Booking.objects.create(package=self.pkg, name="Asha", phone="0712")
        for key in ["bookings", "packages", "destinations", "package-photos", "package-reviews"]:
            self.assertEqual(self.client.get(reverse("dash_manage", args=[key])).status_code, 200, key)
        self.assertContains(self.client.get(reverse("dashboard")), "Honeymoon")
        self.client.post(reverse("dash_manage_action", args=["bookings", b.pk]), {"act": "confirmed"})
        b.refresh_from_db(); self.assertEqual(b.status, "confirmed")


class PasswordResetTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user("amina", "amina@example.com", "Old-pass-123")
        self.member = Member.objects.create(user=self.user, name="Amina Hassan", age=28, gender="F", city="Arusha", phone="0712 345 678")

    def reset(self, value):
        return self.client.post(reverse("password_reset"), {"email": value})

    def test_email_username_or_phone_find_the_account_and_the_link_works(self):
        from django.core import mail
        from django.test import override_settings
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", EMAIL_LIVE=True):
            for value in ["AMINA@example.com", "amina", "+255712345678"]:
                from django.core.cache import cache; cache.clear()
                self.assertRedirects(self.reset(value), reverse("password_reset_done"))
            self.assertEqual(len(mail.outbox), 3)
            self.reset("nobody@example.com")   # unknown: same page, nothing sent
            self.assertEqual(len(mail.outbox), 3)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["amina@example.com"]); self.assertIn("Amina Hassan", msg.body)
        self.assertTrue(any("text/html" in m for _, m in msg.alternatives))
        link = next(w for w in msg.body.split() if "/reset/" in w)
        r = self.client.get(link, follow=True)
        r = self.client.post(r.redirect_chain[-1][0], {"new_password1": "New-pass-456!", "new_password2": "New-pass-456!"})
        self.assertRedirects(r, reverse("password_reset_complete"))
        self.user.refresh_from_db(); self.assertTrue(self.user.check_password("New-pass-456!"))

    def test_when_email_cannot_be_sent_support_gets_a_ticket(self):
        from django.test import override_settings
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend", EMAIL_LIVE=False, DEBUG=False):
            self.assertRedirects(self.reset("amina"), reverse("password_reset_done"))
        t = SupportTicket.objects.get()
        self.assertEqual((t.user, t.subject), (self.user, "Password reset help"))
        with override_settings(EMAIL_BACKEND="core.email_backends.BrevoBackend", EMAIL_LIVE=True, BREVO_API_KEY="x"):
            from unittest import mock
            from django.core.cache import cache; cache.clear()
            with mock.patch("urllib.request.urlopen", side_effect=OSError("network down")):
                self.assertRedirects(self.reset("amina"), reverse("password_reset_done"))
        self.assertEqual(SupportTicket.objects.count(), 1)   # one open ticket is enough

    def test_staff_can_create_a_reset_link_from_the_dashboard(self):
        staff = User.objects.create_user("boss", is_staff=True)
        self.client.force_login(staff)
        SupportTicket.objects.create(user=self.user, subject="Password reset help", message="x")
        r = self.client.post(reverse("dash_member_action", args=[self.member.pk]), {"act": "reset_link"}, follow=True)
        self.assertContains(r, "/account/reset/")
        self.assertEqual(SupportTicket.objects.get().status, "closed")
        r = self.client.post(reverse("dash_member_action", args=[Member.objects.create(user=staff, name="Boss", age=40).pk]), {"act": "reset_link"}, follow=True)
        self.assertNotContains(r, "/account/reset/")

    def test_brevo_backend_sends_json(self):
        import json
        from unittest import mock
        from django.core.mail import EmailMultiAlternatives
        from core.email_backends import BrevoBackend
        from django.test import override_settings
        resp = mock.MagicMock(); resp.__enter__.return_value.status = 201
        with override_settings(BREVO_API_KEY="key-1"), mock.patch("urllib.request.urlopen", return_value=resp) as urlopen:
            m = EmailMultiAlternatives("Hi", "text", "Sakinah <no-reply@sakinah.co.tz>", ["a@example.com"]); m.attach_alternative("<b>hi</b>", "text/html")
            self.assertEqual(BrevoBackend().send_messages([m]), 1)
        req = urlopen.call_args[0][0]
        body = json.loads(req.data)
        self.assertEqual(req.get_header("Api-key"), "key-1")
        self.assertEqual((body["sender"]["email"], body["to"], body["htmlContent"]), ("no-reply@sakinah.co.tz", [{"email": "a@example.com"}], "<b>hi</b>"))


class PublicChatTests(TestCase):
    def setUp(self):
        self.me = User.objects.create_user("juma")
        self.mine = Member.objects.create(user=self.me, name="Juma Ali", age=30, gender="M", city="Arusha")
        self.her_user = User.objects.create_user("amina2")
        self.her = Member.objects.create(user=self.her_user, name="Amina Hassan", age=27, gender="F", city="Arusha")
        self.other = Member.objects.create(name="Zahra Said", age=26, gender="F", city="Mwanza")   # no login yet
        self.plan = Plan.objects.create(name="Chat test", price=5000, daily_messages=-1, daily_call_seconds=0)
        Member.objects.filter(pk=self.mine.pk).update(plan=self.plan, premium_until=timezone.localdate() + timedelta(days=30))
        self.mine.refresh_from_db()
        self.client.force_login(self.me)

    def url(self, m=None):
        return reverse("thread", args=[m.pk]) if m else reverse("inbox")

    def test_the_profile_page_carries_call_buttons(self):
        plan = Plan.objects.create(name="Profile plan", price=20000, daily_messages=10, daily_call_seconds=300)
        Member.objects.filter(pk=self.mine.pk).update(plan=plan, premium_until=timezone.localdate() + timedelta(days=30))
        r = self.client.get(reverse("member", args=[self.her.pk]))
        self.assertContains(r, "Voice Call"); self.assertContains(r, "Video Call")
        self.assertContains(r, 'data-call="video"')
        Plan.objects.filter(pk=plan.pk).update(daily_call_seconds=0)
        r = self.client.get(reverse("member", args=[self.her.pk]))
        self.assertNotContains(r, 'data-call="video"')
        self.assertContains(r, "btn-vid up")                       # it points at the plans instead

    def test_the_match_cards_carry_call_buttons(self):
        plan = Plan.objects.create(name="Call plan", price=20000, daily_messages=10, daily_call_seconds=300)
        Member.objects.filter(pk=self.mine.pk).update(plan=plan, premium_until=timezone.localdate() + timedelta(days=30))
        r = self.client.get(reverse("matches"))
        self.assertContains(r, 'data-call="voice"')
        self.assertContains(r, 'data-call="video"')
        self.assertContains(r, "Piga Simu"); self.assertContains(r, "Video Call")
        self.assertNotContains(r, "Tuma Ujumbe")        # WhatsApp duplicated the chat button; it lives on the profile page
        Plan.objects.filter(pk=plan.pk).update(daily_call_seconds=0)        # no call time on the plan
        r = self.client.get(reverse("matches"))
        self.assertNotContains(r, 'data-call="voice"')
        self.assertContains(r, "pc-b4 up")                                  # it points at the plans instead

    def test_the_call_buttons_always_show_and_say_why_when_they_are_off(self):
        # a member without a login cannot be called at all: grey buttons, with the reason in Swahili
        Plan.objects.filter(pk=self.plan.pk).update(daily_call_seconds=300)
        r = self.client.get(self.url(self.other))
        self.assertContains(r, 'class="ch-ib off"', count=2)
        self.assertContains(r, "bado hajaanza kutumia simu")
        # today's call time spent: still two buttons, now saying so
        Call.objects.create(caller=self.me, callee=self.her_user, status="ended", billed_seconds=300)
        r = self.client.get(self.url(self.her))
        self.assertContains(r, 'class="ch-ib off"', count=2)
        self.assertContains(r, "Umetumia muda wako wote wa simu leo")
        # a plan with no call time at all points at the plans instead
        Plan.objects.filter(pk=self.plan.pk).update(daily_call_seconds=0)
        self.assertContains(self.client.get(self.url(self.her)), "ch-ib up")

    def test_list_search_and_opening_a_chat(self):
        Message.objects.create(sender=self.her_user, to=self.mine, body="Assalamu Alaikum")
        Message.objects.create(sender=self.me, to=self.other, body="Habari ya leo")
        r = self.client.get(self.url())
        self.assertContains(r, "Amina Hassan"); self.assertContains(r, "Zahra Said")
        self.assertContains(r, "Mazungumzo yako")                      # nothing opened yet
        r = self.client.get(self.url(), {"q": "zahra"})
        self.assertContains(r, "Zahra Said"); self.assertNotContains(r, "Amina Hassan")
        r = self.client.get(self.url(self.her))
        self.assertContains(r, "Assalamu Alaikum"); self.assertContains(r, 'id="ch-form"')
        self.assertTrue(Message.objects.get(sender=self.her_user).read)   # opening the chat marks it read

    def test_sending_text_photo_and_voice(self):
        import tempfile
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from PIL import Image
        png = BytesIO(); Image.new("RGB", (400, 300), (200, 80, 120)).save(png, "PNG")
        with tempfile.TemporaryDirectory() as tmp, override_settings(MEDIA_ROOT=tmp):
            self.assertRedirects(self.client.post(self.url(self.her), {"body": "Habari"}), self.url(self.her))
            self.client.post(self.url(self.her), {"body": "", "image": SimpleUploadedFile("p.png", png.getvalue(), "image/png")})
            r = self.client.post(self.url(self.her), {"voice": SimpleUploadedFile("v.webm", b"\x1aE\xdf\xa3" + b"0" * 900, "audio/webm"), "duration": 7},
                                 HTTP_X_REQUESTED_WITH="fetch")
            j = r.json()
            self.assertTrue(j["ok"])
            self.assertIn("data-voice", j["html"])      # the finished bubble comes back, so no page reload is needed
            texts = list(Message.objects.filter(sender=self.me).values_list("body", flat=True))
            self.assertEqual(texts, ["Habari", "", ""])
            self.assertEqual(Message.objects.filter(sender=self.me).last().preview, "🎤 Voice message (0:07)")
            self.assertTrue(Notification.objects.filter(user=self.her_user, title__startswith="Ujumbe mpya").exists())
            self.assertEqual(self.client.post(self.url(self.her), {"body": ""}, HTTP_X_REQUESTED_WITH="fetch").status_code, 400)

    def test_blocks_and_message_rules_are_respected(self):
        Block.objects.create(user=self.me, member=self.her)
        self.client.post(self.url(self.her), {"body": "hujambo"})
        self.assertFalse(Message.objects.exists())
        self.assertContains(self.client.get(self.url(self.her)), "Umemzuia mwanachama huyu")
        self.assertNotContains(self.client.get(self.url()), "Amina Hassan")     # blocked people leave the list
        Block.objects.all().delete()
        Block.objects.create(user=self.her_user, member=self.mine)              # she blocked me
        self.client.post(self.url(self.her), {"body": "hujambo"})
        self.assertFalse(Message.objects.exists())
        Block.objects.all().delete()
        self.her.allow_messages_from = "matched"; self.her.save()
        self.client.post(self.url(self.her), {"body": "hujambo"})
        self.assertFalse(Message.objects.exists())
        self.assertContains(self.client.get(self.url(self.her)), "anapokea ujumbe kutoka")

    def test_feed_brings_new_messages_only(self):
        first = Message.objects.create(sender=self.me, to=self.her, body="Ya kwanza")
        r = self.client.get(reverse("thread_feed", args=[self.her.pk]), {"after": first.pk}).json()
        self.assertEqual((r["html"], r["last"]), ("", first.pk))
        new = Message.objects.create(sender=self.her_user, to=self.mine, body="Jibu langu")
        r = self.client.get(reverse("thread_feed", args=[self.her.pk]), {"after": first.pk}).json()
        self.assertIn("Jibu langu", r["html"]); self.assertEqual(r["last"], new.pk)
        self.assertNotIn("Ya kwanza", r["html"])
        new.refresh_from_db(); self.assertTrue(new.read)                        # reading the feed marks them read

    def test_messages_are_grouped_by_day_and_sender(self):
        from core.views import mark_groups
        a = Message.objects.create(sender=self.me, to=self.her, body="1")
        b = Message.objects.create(sender=self.me, to=self.her, body="2")
        c = Message.objects.create(sender=self.her_user, to=self.mine, body="3")
        Message.objects.filter(pk=a.pk).update(created=a.created - timedelta(days=1))
        msgs = mark_groups(list(Message.objects.filter(pk__in=[a.pk, b.pk, c.pk]).order_by("created")))
        self.assertEqual([m.show_day for m in msgs], [True, True, False])      # a new day starts at b
        self.assertEqual([m.show_av for m in msgs], [True, True, True])        # b starts the day, c changes sender


class PlanAllowanceTests(TestCase):
    """What each plan may send and call in 24 hours."""
    def setUp(self):
        self.me = User.objects.create_user("juma3")
        self.mine = Member.objects.create(user=self.me, name="Juma Ali", age=30, gender="M", city="Arusha")
        self.her_user = User.objects.create_user("amina3")
        self.her = Member.objects.create(user=self.her_user, name="Amina Hassan", age=27, gender="F", city="Arusha")
        self.client.force_login(self.me)

    def on(self, messages_a_day, call_seconds):
        plan = Plan.objects.create(name="Test", price=1000, daily_messages=messages_a_day, daily_call_seconds=call_seconds)
        Member.objects.filter(pk=self.mine.pk).update(plan=plan, premium_until=timezone.localdate() + timedelta(days=30))
        self.mine.refresh_from_db()
        return plan

    def send(self, body="Habari"):
        return self.client.post(reverse("thread", args=[self.her.pk]), {"body": body})

    def test_a_member_without_a_plan_can_read_but_not_send(self):
        r = self.client.get(reverse("thread", args=[self.her.pk]))
        self.assertContains(r, "hakikuruhusu kuanzisha mazungumzo")
        self.send()
        self.assertEqual(Message.objects.count(), 0)

    def test_a_plan_stops_at_its_daily_count_of_new_conversations(self):
        self.on(2, 30)
        others = [Member.objects.create(user=User.objects.create_user(f"mtu{i}"), name=f"Mtu {i}", age=25, gender="F", city="Tanga")
                  for i in range(3)]
        for m in others[:2]: self.client.post(reverse("thread", args=[m.pk]), {"body": "Salaam"})
        self.assertEqual(Message.objects.count(), 2)
        self.client.post(reverse("thread", args=[others[2].pk]), {"body": "Salaam"})
        self.assertEqual(Message.objects.count(), 2)                       # the third conversation is refused
        self.assertEqual(self.mine.messages_left, 0)
        r = self.client.get(reverse("thread", args=[others[2].pk]))
        self.assertContains(r, "kikomo cha mazungumzo mapya ya leo")

    def test_unlimited_means_unlimited(self):
        self.on(-1, -1)
        for i in range(12):
            self.send(f"Ujumbe {i}")
        self.assertEqual(Message.objects.count(), 12)
        self.assertEqual(self.mine.messages_left, -1)
        self.assertTrue(self.mine.can_send_messages)

    def test_call_logs_do_not_eat_the_message_allowance(self):
        self.on(2, 60)
        Message.objects.create(sender=self.her_user, to=self.mine, body="Missed voice call", kind="call")
        Message.objects.create(sender=self.me, to=self.her, body="Voice call", kind="call")
        self.assertEqual(self.mine.messages_left, 2)

    def test_calls_need_call_time_on_the_plan(self):
        from members.calls import call_permission
        self.assertEqual(call_permission(self.mine, self.her), (False, "premium"))   # no plan at all
        self.on(10, 30)
        self.assertEqual(call_permission(self.mine, self.her), (True, ""))
        Call.objects.create(caller=self.me, callee=self.her_user, kind="voice", status="ended",
                            answered_at=timezone.now(), ended_at=timezone.now(), billed_seconds=30)
        self.assertEqual(self.mine.call_seconds_left, 0)
        self.assertEqual(call_permission(self.mine, self.her), (False, "spent"))

    def test_a_call_is_capped_at_the_time_that_is_left_and_is_billed(self):
        from members.calls import call_cap, finish
        self.on(10, 90)
        Call.objects.create(caller=self.me, callee=self.her_user, status="ended", billed_seconds=60)
        call = Call.objects.create(caller=self.me, callee=self.her_user, status="accepted",
                                   answered_at=timezone.now() - timedelta(seconds=5))
        self.assertEqual(call_cap(call), 30)                               # 90 allowed, 60 already spent
        finish(call, "ended")
        call.refresh_from_db()
        self.assertGreaterEqual(call.billed_seconds, 5)

    def test_the_plan_card_prints_the_allowance(self):
        plan = Plan.objects.create(name="Gold test", price=50000, daily_messages=100, daily_call_seconds=300)
        self.assertEqual(plan.allowance_lines, [(True, "Start 100 new chats a day"), (True, "5 minutes of calls a day")])
        free = Plan.objects.create(name="Free test", price=0)
        self.assertEqual(free.allowance_lines, [(False, "Cannot start a chat"), (False, "No voice or video calls")])


class ReplyRuleTests(TestCase):
    """Starting a conversation needs a plan; answering one does not, but it is one answer per message."""
    def setUp(self):
        self.me = User.objects.create_user("hamisi")
        self.mine = Member.objects.create(user=self.me, name="Hamisi Juma", age=32, gender="M", city="Mbeya")
        self.her_user = User.objects.create_user("rehema")
        self.her = Member.objects.create(user=self.her_user, name="Rehema Ally", age=28, gender="F", city="Mbeya")
        self.plan = Plan.objects.create(name="Gold", price=50000, daily_messages=2, daily_call_seconds=300)
        self.client.force_login(self.me)                      # Hamisi has no plan

    def url(self, m): return reverse("thread", args=[m.pk])
    def paid(self, member):
        Member.objects.filter(pk=member.pk).update(plan=self.plan, premium_until=timezone.localdate() + timedelta(days=30))
        member.refresh_from_db()

    def mine_sent(self): return Message.objects.filter(sender=self.me, to=self.her).count()

    def test_without_a_plan_he_cannot_write_first(self):
        self.client.post(self.url(self.her), {"body": "Hujambo"})
        self.assertEqual(self.mine_sent(), 0)
        self.assertContains(self.client.get(self.url(self.her)), "hakikuruhusu kuanzisha mazungumzo")

    def test_she_writes_first_and_he_may_answer_once(self):
        self.paid(self.her)
        Message.objects.create(sender=self.her_user, to=self.mine, body="Assalamu Alaikum")
        self.client.post(self.url(self.her), {"body": "Wa alaikum salaam"})
        self.assertEqual(self.mine_sent(), 1)
        self.client.post(self.url(self.her), {"body": "Na habari za siku?"})      # a second answer is his turn used up
        self.assertEqual(self.mine_sent(), 1)
        self.assertContains(self.client.get(self.url(self.her)), "Umeshajibu ujumbe wake")
        Message.objects.create(sender=self.her_user, to=self.mine, body="Nzuri sana")
        self.client.post(self.url(self.her), {"body": "Alhamdulillah"})           # she wrote again, so he may too
        self.assertEqual(self.mine_sent(), 2)

    def test_a_call_log_is_not_a_message_he_can_answer(self):
        Message.objects.create(sender=self.her_user, to=self.mine, body="Missed voice call", kind="call")
        self.client.post(self.url(self.her), {"body": "Nimekukosa"})
        self.assertEqual(self.mine_sent(), 0)

    def test_a_paying_member_keeps_writing_without_waiting(self):
        self.paid(self.mine)
        self.client.post(self.url(self.her), {"body": "Assalamu Alaikum"})
        for i in range(3): self.client.post(self.url(self.her), {"body": f"Ujumbe {i}"})
        self.assertEqual(self.mine_sent(), 4)                 # one start plus three follow-ups, no answer needed

    def test_the_daily_count_is_about_starting_not_about_every_message(self):
        self.paid(self.mine)
        third = Member.objects.create(user=User.objects.create_user("zuhura"), name="Zuhura", age=26, gender="F", city="Dodoma")
        self.client.post(self.url(self.her), {"body": "Salaam"})
        self.client.post(self.url(third), {"body": "Salaam"})
        self.assertEqual(self.mine.messages_left, 0)          # two starts on a plan that allows two
        self.client.post(self.url(self.her), {"body": "Tena"})
        self.assertEqual(self.mine_sent(), 2)                 # the open chat still takes messages
        fourth = Member.objects.create(user=User.objects.create_user("sadia"), name="Sadia", age=24, gender="F", city="Tanga")
        self.client.post(self.url(fourth), {"body": "Salaam"})
        self.assertEqual(Message.objects.filter(sender=self.me, to=fourth).count(), 0)   # but no new one today
