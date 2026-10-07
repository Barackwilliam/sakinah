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
