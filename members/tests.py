from datetime import date, timedelta
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from core.models import (Block, Event, EventRegistration, Like, Member, Message, Notification, Payment, Plan, ProfileView,
                         SupportTicket)

PAGES = ["m_dashboard", "m_find", "m_matches", "m_messages", "m_profile", "m_profile_edit", "m_photos", "m_prefs", "m_verify",
         "m_views", "m_liked", "m_activity", "m_events", "m_membership", "m_safety", "m_settings", "m_password", "m_help",
         "m_notifications"]

class MemberAreaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("juma", "juma@example.com", "S3cure-pass-123")
        self.me = Member.objects.create(user=self.user, name="Juma Ali", age=30, gender="M", city="Arusha", occupation="Teacher")
        self.amina_user = User.objects.create_user("amina", "amina@example.com", "S3cure-pass-123")
        self.amina = Member.objects.create(user=self.amina_user, name="Amina Hassan", age=27, gender="F", city="Arusha",
                                           occupation="Nurse", verified=True)
        self.client.login(username="juma", password="S3cure-pass-123")

    def test_every_page_loads(self):
        for name in PAGES:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        for tab in ["compare", "mine", "history", "benefits", "faq"]:
            self.assertEqual(self.client.get(reverse("m_membership"), {"tab": tab}).status_code, 200, tab)
        for tab in ["privacy", "features", "verification", "blocked", "report"]:
            self.assertEqual(self.client.get(reverse("m_safety"), {"tab": tab}).status_code, 200, tab)
        for tab in ["views", "likes", "matches", "messages", "saved", "search"]:
            self.assertEqual(self.client.get(reverse("m_activity"), {"tab": tab}).status_code, 200, tab)

    def test_login_required_and_member_redirect(self):
        self.client.logout()
        url = reverse("m_dashboard")
        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")
        r = self.client.post(reverse("login"), {"username": "juma", "password": "S3cure-pass-123"})
        self.assertRedirects(r, url)

    def test_find_shows_opposite_gender_and_bad_age_is_ignored(self):
        r = self.client.get(reverse("m_find"))
        self.assertContains(r, "Amina"); self.assertNotContains(r, "Juma Ali,")
        self.assertEqual(self.client.get(reverse("m_views"), {"age": "abc"}).status_code, 200)

    def test_send_message_and_unread_count(self):
        url = reverse("m_messages_with", args=[self.amina.pk])
        self.assertRedirects(self.client.post(url, {"body": "Assalamu Alaikum"}), url)
        msg = Message.objects.get(sender=self.user, to=self.amina)
        self.assertEqual(msg.body, "Assalamu Alaikum")
        self.assertTrue(Notification.objects.filter(user=self.amina_user, title__contains="Juma").exists())
        self.client.login(username="amina", password="S3cure-pass-123")
        self.assertContains(self.client.get(reverse("m_messages")), "Assalamu Alaikum")
        self.client.get(reverse("m_messages_with", args=[self.me.pk]))
        msg.refresh_from_db(); self.assertTrue(msg.read)

    def test_message_rules(self):
        self.amina.allow_messages_from = "verified"; self.amina.save()
        self.client.post(reverse("m_messages_with", args=[self.amina.pk]), {"body": "Hi"})
        self.assertFalse(Message.objects.exists())
        self.amina.allow_messages_from = "all"; self.amina.save()
        Block.objects.create(user=self.amina_user, member=self.me)
        self.client.post(reverse("m_messages_with", args=[self.amina.pk]), {"body": "Hi"})
        self.assertFalse(Message.objects.exists())
        self.assertEqual(self.client.get(reverse("member", args=[self.amina.pk])).status_code, 404)

    def test_block_hides_member(self):
        self.client.post(reverse("m_block", args=[self.amina.pk]))
        self.assertTrue(Block.objects.filter(user=self.user, member=self.amina).exists())
        self.assertNotContains(self.client.get(reverse("m_find"), {"q": "Amina"}), "Amina, 27")
        self.client.post(reverse("m_block", args=[self.amina.pk]))
        self.assertFalse(Block.objects.exists())

    def test_like_notifies_and_mutual_match(self):
        self.client.post(reverse("like", args=[self.amina.pk]))
        self.assertTrue(Notification.objects.filter(user=self.amina_user, title="Juma Ali liked your profile").exists())
        self.client.login(username="amina", password="S3cure-pass-123")
        self.client.post(reverse("like", args=[self.me.pk]))
        self.assertTrue(Notification.objects.filter(user=self.user, title__startswith="It's a match").exists())
        self.assertContains(self.client.get(reverse("m_matches"), {"tab": "mutual"}), "Juma")

    def test_who_liked_me_is_locked_for_free_members(self):
        Like.objects.create(user=self.amina_user, member=self.me)
        r = self.client.get(reverse("m_liked"))
        self.assertContains(r, "Upgrade to see")
        self.me.plan = Plan.objects.create(name="Gold", price=50000)
        self.me.premium_until = date.today() + timedelta(days=30); self.me.save()
        r = self.client.get(reverse("m_liked"))
        self.assertNotContains(r, "Upgrade to see"); self.assertContains(r, "Amina")

    def test_profile_views_are_recorded_once(self):
        self.client.get(reverse("member", args=[self.amina.pk]))
        self.client.get(reverse("member", args=[self.amina.pk]))
        self.assertEqual(ProfileView.objects.filter(viewer=self.user, member=self.amina).count(), 1)
        self.client.login(username="amina", password="S3cure-pass-123")
        self.assertContains(self.client.get(reverse("m_views")), "Juma")

    def test_privacy_and_visibility(self):
        r = self.client.post(reverse("m_safety"), {"profile_visibility": "hidden", "photo_visibility": "verified", "location_display": "city",
                                                  "allow_messages_from": "matched", "show_age": "on"})
        self.assertEqual(r.status_code, 302)
        self.me.refresh_from_db()
        self.assertEqual((self.me.profile_visibility, self.me.allow_messages_from, self.me.show_online), ("hidden", "matched", False))
        self.client.post(reverse("m_visibility"), {"profile_visibility": "all"})
        self.me.refresh_from_db(); self.assertEqual(self.me.profile_visibility, "all")

    def test_settings_sections_save_separately(self):
        r = self.client.post(reverse("m_settings"), {"section": "notify", "notify-notify_messages": "on"})
        self.assertEqual(r.status_code, 302)
        self.me.refresh_from_db()
        self.assertTrue(self.me.notify_messages); self.assertFalse(self.me.notify_likes)
        self.assertEqual(self.me.occupation, "Teacher")
        self.client.post(reverse("m_settings"), {"section": "prefs", "prefs-pref_age_min": "35", "prefs-pref_age_max": "25"})
        self.me.refresh_from_db(); self.assertIsNone(self.me.pref_age_min)
        self.client.post(reverse("m_settings"), {"section": "look", "look-ui_language": "en", "look-ui_theme": "dark"})
        self.assertContains(self.client.get(reverse("m_dashboard")), 'data-theme="dark"')

    def test_payment_request_is_pending(self):
        plan = Plan.objects.create(name="Gold", price=50000)
        r = self.client.post(reverse("m_membership"), {"plan": plan.pk, "months": 3, "gateway": "mpesa", "phone": "0712345678", "reference": "QWE123"})
        self.assertRedirects(r, reverse("m_membership") + "?tab=history")
        p = Payment.objects.get(user=self.user)
        self.assertEqual((p.status, p.amount, p.months), ("pending", 150000, 3))
        self.me.refresh_from_db(); self.assertFalse(self.me.is_premium)

    def test_help_ticket_and_verification(self):
        self.client.post(reverse("m_help"), {"kind": "report", "subject": "Fake profile", "message": "Please check"})
        self.assertTrue(SupportTicket.objects.filter(user=self.user, kind="report").exists())
        self.client.post(reverse("m_verify"), {"subject": "Verify me", "message": "ID attached"})
        self.assertFalse(SupportTicket.objects.filter(kind="verification").exists())

    def test_event_registration_rules(self):
        past = Event.objects.create(title="Old", date=date.today() - timedelta(days=3), city="Arusha")
        full = Event.objects.create(title="Full", date=date.today() + timedelta(days=3), city="Arusha", capacity=1)
        EventRegistration.objects.create(event=full, user=self.amina_user)
        open_ = Event.objects.create(title="Open", date=date.today() + timedelta(days=5), city="Arusha")
        for e in (past, full, open_): self.client.post(reverse("event_register", args=[e.pk]))
        self.assertEqual(list(EventRegistration.objects.filter(user=self.user).values_list("event__title", flat=True)), ["Open"])
        self.assertContains(self.client.get(reverse("m_events"), {"tab": "mine"}), "Open")
        self.assertEqual(self.client.get(reverse("m_event", args=[open_.pk])).status_code, 200)

    def test_delete_account_needs_password(self):
        self.client.post(reverse("m_delete"), {"password": "wrong"})
        self.assertTrue(User.objects.filter(username="juma").exists())
        self.client.post(reverse("m_delete"), {"password": "S3cure-pass-123"})
        self.assertFalse(User.objects.filter(username="juma").exists())

    def test_export_and_deactivate(self):
        r = self.client.get(reverse("m_export"))
        self.assertEqual(r["Content-Type"], "application/json"); self.assertIn(b"Juma Ali", r.content)
        self.client.post(reverse("m_deactivate"))
        self.me.refresh_from_db(); self.assertEqual(self.me.profile_visibility, "hidden")
