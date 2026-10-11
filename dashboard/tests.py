import os
from datetime import timedelta
from unittest import mock
from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from core.models import Broadcast, Member, Message, Notification, Payment, Plan

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class DashboardTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("boss", "boss@example.com", "S3cure-pass-123", is_staff=True)
        self.user = User.objects.create_user("juma", "juma@example.com", "S3cure-pass-123")
        self.juma = Member.objects.create(user=self.user, name="Juma", age=30, gender="M", city="Arusha", occupation="Teacher")
        u2 = User.objects.create_user("asha", "asha@example.com", "S3cure-pass-123")
        self.asha = Member.objects.create(user=u2, name="Asha", age=25, gender="F", city="Dodoma", occupation="Nurse", verified=True)
        self.gold = Plan.objects.create(name="Gold", price=50000)

    def test_only_staff_can_open_dashboard(self):
        url = reverse("dashboard")
        self.assertRedirects(self.client.get(url), f"{reverse('login')}?next={url}")
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(url), reverse("home"))
        self.client.force_login(self.admin)
        for name in ["dashboard", "dash_members", "dash_comms", "dash_payments", "dash_report", "dash_payments_csv"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertContains(self.client.get(reverse("dash_search"), {"q": "Asha"}), "Asha")

    def test_admin_login_tab_lands_on_dashboard(self):
        r = self.client.post(reverse("login"), {"username": "boss@example.com", "password": "S3cure-pass-123", "next": reverse("dashboard")})
        self.assertRedirects(r, reverse("dashboard"))

    def test_verify_member_sends_notification(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("dash_member_action", args=[self.juma.pk]), {"act": "verify"})
        self.juma.refresh_from_db(); self.assertTrue(self.juma.verified)
        self.assertTrue(Notification.objects.filter(user=self.user).exists())

    def test_broadcast_channels_and_filters(self):
        self.client.force_login(self.admin)
        url = reverse("dash_comms")
        self.client.post(url, {"channel": "notification", "subject": "Hello", "body": "Hi {name}", "gender": "F"})
        n = Notification.objects.get(); self.assertEqual((n.user, n.body), (self.asha.user, "Hi Asha"))
        self.client.post(url, {"channel": "inapp", "subject": "Seminar", "body": "Come {name}", "verified": "yes"})
        self.assertEqual(Message.objects.get().to, self.asha)
        self.client.post(url, {"channel": "email", "subject": "News", "body": "Dear {name}"})
        self.assertEqual(len(mail.outbox), 2)
        self.client.post(url, {"channel": "email", "subject": "Later", "body": "x", "draft": "1"})
        self.assertEqual(Broadcast.objects.filter(status="draft").count(), 1)
        self.client.post(url, {"channel": "email", "subject": "", "body": "", "city": "Dodoma", "preview": "1"})
        self.assertEqual(Broadcast.objects.count(), 4)
        self.assertEqual(self.client.get(url, {"city": "Dodoma"}).context["estimate"], 1)

    def test_member_notification_page(self):
        Notification.objects.create(user=self.user, title="Welcome")
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("notifications")), "Welcome")
        self.assertFalse(Notification.objects.filter(read=False).exists())

    def test_manual_payment_activates_and_extends_plan(self):
        self.client.force_login(self.admin)
        data = {"member": self.juma.pk, "kind": "premium", "plan": self.gold.pk, "months": 3, "amount": 150000, "gateway": "mpesa", "status": "completed"}
        self.client.post(reverse("dash_payments"), data)
        p = Payment.objects.get(); self.juma.refresh_from_db()
        self.assertEqual((p.payer_name, p.user), ("Juma", self.user))
        self.assertTrue(p.invoice_no.startswith(f"INV-{timezone.now().year}-"))
        self.assertTrue(self.juma.is_premium)
        first_end = self.juma.premium_until
        self.assertGreater(first_end, timezone.localdate() + timedelta(days=85))
        self.client.post(reverse("dash_payments"), {**data, "months": 1, "amount": 50000})
        self.juma.refresh_from_db(); self.assertGreater(self.juma.premium_until, first_end)
        self.assertEqual(Payment.objects.count(), 2)
        self.assertNotEqual(*Payment.objects.values_list("invoice_no", flat=True))

    def test_pending_payment_confirm_and_refund(self):
        self.client.force_login(self.admin)
        p = Payment.objects.create(user=self.user, payer_name="Juma", kind="premium", plan=self.gold, amount=50000, status="pending")
        self.client.post(reverse("dash_payment_action", args=[p.pk]), {"act": "complete"})
        p.refresh_from_db(); self.juma.refresh_from_db()
        self.assertEqual(p.status, "completed"); self.assertTrue(self.juma.is_premium)
        self.client.post(reverse("dash_payment_action", args=[p.pk]), {"act": "refund"})
        p.refresh_from_db(); self.assertEqual(p.status, "refunded")
        self.assertContains(self.client.get(reverse("dash_receipt", args=[p.pk])), p.invoice_no)

    def test_payment_needs_payer_and_plan(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("dash_payments"), {"kind": "premium", "months": 1, "amount": 1000, "gateway": "cash", "status": "completed"})
        self.assertEqual(r.status_code, 200); self.assertFalse(Payment.objects.exists())

    def test_ensure_admin_command(self):
        with mock.patch.dict(os.environ, {"ADMIN_EMAIL": "owner@example.com", "ADMIN_PASSWORD": "S3cure-pass-123", "ADMIN_USERNAME": "owner"}):
            call_command("ensure_admin"); call_command("ensure_admin")
        u = User.objects.get(username="owner"); self.assertTrue(u.is_superuser)


class AdminAreaTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("boss", "boss@example.com", "S3cure-pass-123", is_staff=True)
        self.root = User.objects.create_superuser("root", "root@example.com", "S3cure-pass-123")
        self.u1 = User.objects.create_user("juma", "juma@example.com", "S3cure-pass-123")
        self.juma = Member.objects.create(user=self.u1, name="Juma Ali", age=30, gender="M", city="Arusha", occupation="Teacher")
        self.u2 = User.objects.create_user("asha", "asha@example.com", "S3cure-pass-123")
        self.asha = Member.objects.create(user=self.u2, name="Asha Said", age=25, gender="F", city="Dodoma", occupation="Nurse", verified=True)
        self.client.force_login(self.admin)

    def test_login_sends_staff_and_members_to_their_dashboards(self):
        self.client.logout()
        self.assertRedirects(self.client.post(reverse("login"), {"username": "boss", "password": "S3cure-pass-123"}), reverse("dashboard"))
        self.client.logout()
        self.assertRedirects(self.client.post(reverse("login"), {"username": "juma", "password": "S3cure-pass-123"}), reverse("m_dashboard"))

    def test_pages_and_variants(self):
        from core.models import Like
        Like.objects.create(user=self.u1, member=self.asha); Like.objects.create(user=self.u2, member=self.juma)
        Message.objects.create(sender=self.u1, to=self.asha, body="Assalamu Alaikum")
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, "Admin Dashboard"); self.assertContains(r, "Latest Matches"); self.assertContains(r, "Contacted")
        for url in [reverse("dash_members"), reverse("dash_matches"), reverse("dash_matches") + "?tab=all", reverse("dash_matches") + "?tab=messages",
                    reverse("dash_matches") + f"?tab=messages&a={self.juma.pk}&b={self.asha.pk}", reverse("dashboard") + "?range=6",
                    reverse("dash_members") + "?f=pending&gender=M&age=26-35&plan=free&status=pending&per=25"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertContains(self.client.get(reverse("dash_matches")), "Juma Ali")
        self.client.force_login(self.root)
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, "Welcome, Super Admin"); self.assertContains(r, "Latest Registrations")

    def test_member_filters_and_tabs(self):
        self.juma.status = "suspended"; self.juma.save()
        r = self.client.get(reverse("dash_members"), {"f": "suspended"})
        self.assertContains(r, "Juma Ali"); self.assertNotContains(r, "Asha Said")
        r = self.client.get(reverse("dash_members"), {"q": "asha"})
        self.assertContains(r, "Asha Said"); self.assertNotContains(r, "Juma Ali")

    def test_single_and_bulk_actions(self):
        url = reverse("dash_member_action", args=[self.juma.pk])
        self.client.post(url, {"act": "suspend"})
        self.juma.refresh_from_db(); self.assertEqual(self.juma.status, "suspended")
        self.assertTrue(Notification.objects.filter(user=self.u1, title__contains="suspended").exists())
        bulk = reverse("dash_members_bulk")
        self.client.post(bulk, {"act": "activate", "ids": [self.juma.pk, self.asha.pk]})
        self.juma.refresh_from_db(); self.assertEqual(self.juma.status, "active")
        self.client.post(bulk, {"act": "message", "ids": [self.juma.pk], "subject": "Hello", "body": "Hi {name}"})
        self.assertTrue(Notification.objects.filter(user=self.u1, title="Hello", body="Hi Juma").exists())
        r = self.client.post(bulk, {"act": "export", "ids": [self.asha.pk]})
        self.assertEqual(r["Content-Type"], "text/csv"); self.assertIn(b"Asha Said", r.content); self.assertNotIn(b"Juma Ali", r.content)
        staff_member = Member.objects.create(user=self.admin, name="Boss", age=40, gender="M", city="Arusha", occupation="Admin")
        self.client.post(bulk, {"act": "delete", "ids": [staff_member.pk, self.asha.pk]})
        self.assertTrue(Member.objects.filter(pk=staff_member.pk).exists())
        self.assertFalse(User.objects.filter(username="asha").exists())

    def test_suspended_member_is_hidden_and_locked_out(self):
        self.juma.status = "suspended"; self.juma.save()
        self.client.force_login(self.u2)
        self.assertEqual(self.client.get(reverse("member", args=[self.juma.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("matches"), {"seek": "M"}), "Juma Ali")
        self.client.force_login(self.u1)
        self.assertContains(self.client.get(reverse("m_dashboard")), "Your account is suspended")
        self.assertEqual(self.client.get(reverse("m_help")).status_code, 200)

    def test_import_and_export_csv(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        data = "name,age,gender,city,occupation\nHalima Juma,27,F,Tanga,Teacher\nBad Row,12,F,Tanga,\n".encode()
        self.client.post(reverse("dash_members_import"), {"file": SimpleUploadedFile("m.csv", data, content_type="text/csv")})
        self.assertTrue(Member.objects.filter(name="Halima Juma", age=27, gender="F").exists())
        self.assertFalse(Member.objects.filter(name="Bad Row").exists())
        r = self.client.get(reverse("dash_members_csv"), {"gender": "F"})
        self.assertIn(b"Halima Juma", r.content); self.assertNotIn(b"Juma Ali", r.content)
