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
        self.assertRedirects(r, reverse("profile_edit"))
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
        r = self.client.post(reverse("profile_edit"), dict(name="Juma A.", age=31, gender="M", city="Mwanza", occupation="Teacher",
                                                           religion="Islam", marital_status="single", origin="Mtanzania", bio="Hello"))
        me = Member.objects.get(user__username="juma")
        self.assertRedirects(r, reverse("member", args=[me.pk]))
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
        self.assertRedirects(self.signup_external(), reverse("profile_edit"))

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
            self.assertRedirects(self.client.post(reverse("login"), {"username": name, "password": "S3cure-pass-123"}), reverse("home"))
            self.client.logout()
        r = self.client.post(reverse("login"), {"username": "zuhura@example.com", "password": "wrong"})
        self.assertEqual(r.status_code, 200)

    def test_login_page_uses_site_settings(self):
        r = self.client.get(reverse("login"))
        self.assertContains(r, "Sakinah")
        self.assertContains(r, "Karibu tena")


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
        p = Plan.objects.create(name="Gold", price=50000, features="Unlimited messages\n-Incognito mode", popular=True)
        self.assertEqual(p.feature_list, [(True, "Unlimited messages"), (False, "Incognito mode")])
        r = self.client.get(reverse("premium"))
        self.assertContains(r, "Most Popular"); self.assertContains(r, "Incognito mode")
