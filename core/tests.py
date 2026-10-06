from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from .models import Like, Member

class FlowTests(TestCase):
    def setUp(self):
        self.amina = Member.objects.create(name="Amina", age=28, gender="F", city="Arusha", occupation="Accountant", verified=True)
        self.omar = Member.objects.create(name="Omar", age=40, gender="M", city="Dar es Salaam", occupation="Engineer")

    def signup(self, **kw):
        data = dict(username="juma", name="Juma Ali", email="juma@example.com", gender="M", age=30, city="Arusha",
                    occupation="Teacher", password1="S3cure-pass-123", password2="S3cure-pass-123", **kw)
        return self.client.post(reverse("signup"), data)

    def test_pages_load(self):
        for name in ["home", "matches", "events", "services", "premium", "login", "signup"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertContains(self.client.get(reverse("member", args=[self.amina.pk])), "Amina")

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
                                                           intention="Marriage-oriented", religion="Islam", bio="Hello"))
        me = Member.objects.get(user__username="juma")
        self.assertRedirects(r, reverse("member", args=[me.pk]))
        self.assertEqual((me.city, me.bio), ("Mwanza", "Hello"))

    def test_logout(self):
        self.signup()
        self.assertRedirects(self.client.post(reverse("logout")), reverse("home"))
        self.assertContains(self.client.get(reverse("home")), "Join Free")
