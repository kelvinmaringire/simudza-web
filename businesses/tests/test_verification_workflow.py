from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from businesses.models import Business
from businesses.services import owner_save_product
from businesses.verification.levels import LifecycleStatus, VerificationLevel, TRUSTED_LEVELS
from businesses.verification.workflow import (
    businesses_due_for_reminder,
    verification_exceptions,
)
from categories.models import Category
from products.models import Product
from reviews.models import BusinessReview, ProductReview, ReportReason, ReportStatus

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


def days_ago(days):
    return timezone.now() - timedelta(days=days)


@override_settings(EMAIL_BACKEND=EMAIL_BACKEND)
class VerificationWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user("owner", "owner@example.com", "pass")
        self.other = User.objects.create_user("other", "other@example.com", "pass")
        self.staff = User.objects.create_user(
            "staff", "staff@example.com", "pass", is_staff=True
        )
        self.category = Category.objects.create(name="Cat", slug="cat")
        self.business = Business.objects.create(
            name="Owned Co",
            slug="owned-co",
            owner=self.owner,
            confirmed_owner=self.owner,
            verified_at=days_ago(120),
        )
        self.product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Owned Item",
            slug="owned-item",
            verified_at=days_ago(120),
        )
        from products.test_helpers import add_sellable_variant

        self.variant = add_sellable_variant(self.product, price="10.00")
        self.orphan = Business.objects.create(
            name="Orphan Co",
            slug="orphan-co",
            verified_at=days_ago(200),
        )
        self.client = Client()

    # --- Manufacturer verifies ---------------------------------------------

    def test_owner_confirms_everything(self):
        self.business.verification_reminder_sent_at = days_ago(5)
        self.business.save()
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("accounts:owner_confirm"),
            {"kind": "all", "business": self.business.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.business.refresh_from_db()
        self.product.refresh_from_db()
        self.assertGreater(self.business.verified_at, days_ago(1))
        self.assertEqual(
            self.business.verification_level,
            VerificationLevel.SOURCE_VERIFIED,
        )
        self.assertEqual(self.business.verified_by, self.owner)
        self.assertIsNone(self.business.verification_reminder_sent_at)
        self.assertGreater(self.product.verified_at, days_ago(1))
        self.assertEqual(
            self.product.verification_level,
            VerificationLevel.SOURCE_VERIFIED,
        )

    def test_owner_confirm_keeps_simudza_verified_level(self):
        for listing in (self.business, self.product):
            listing.verification_level = VerificationLevel.SIMUDZA_VERIFIED
            listing.save(update_fields=["verification_level"])
        self.client.force_login(self.owner)
        self.client.post(
            reverse("accounts:owner_confirm"),
            {"kind": "all", "business": self.business.pk},
        )
        for listing in (self.business, self.product):
            listing.refresh_from_db()
            self.assertEqual(
                listing.verification_level, VerificationLevel.SIMUDZA_VERIFIED
            )
            self.assertGreater(listing.verified_at, days_ago(1))

    def test_owner_confirm_single_product(self):
        self.client.force_login(self.owner)
        self.client.post(
            reverse("accounts:owner_confirm"),
            {"kind": "product", "business": self.business.pk, "pk": self.product.pk},
        )
        self.product.refresh_from_db()
        self.business.refresh_from_db()
        self.assertGreater(self.product.verified_at, days_ago(1))
        self.assertLess(self.business.verified_at, days_ago(100))

    def test_non_owner_cannot_confirm(self):
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("accounts:owner_confirm"),
            {"kind": "all", "business": self.business.pk},
        )
        self.assertEqual(response.status_code, 404)
        self.business.refresh_from_db()
        self.assertLess(self.business.verified_at, days_ago(100))

    def test_owner_confirm_does_not_resolve_customer_reports(self):
        report = BusinessReview.objects.create(
            business=self.business,
            reason=ReportReason.BUSINESS_CLOSED,
            status=ReportStatus.OPEN,
        )
        self.client.force_login(self.owner)
        self.client.post(
            reverse("accounts:owner_confirm"),
            {"kind": "business", "business": self.business.pk},
        )
        report.refresh_from_db()
        self.assertEqual(report.status, ReportStatus.OPEN)

    def test_owner_product_update_counts_as_verification(self):
        self.business.confirmed_owner = self.owner
        self.business.save(update_fields=["confirmed_owner"])
        owner_save_product(
            self.owner,
            self.business,
            {
                "name": "Owned Item v2",
                "category": self.category,
                "price": Decimal("11.00"),
            },
            product=self.product,
        )
        self.product.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(self.product.name, "Owned Item v2")
        self.assertEqual(self.variant.price, Decimal("11.00"))
        self.assertGreater(self.product.verified_at, days_ago(1))
        self.assertEqual(
            self.product.verification_level,
            VerificationLevel.SOURCE_VERIFIED,
        )

    def test_owner_edit_of_simudza_verified_drops_level_and_emails_superusers(self):
        User = get_user_model()
        User.objects.create_superuser("root", "root@example.com", "pass")
        User.objects.create_superuser("quiet", "", "pass")
        self.product.verification_level = VerificationLevel.SIMUDZA_VERIFIED
        self.product.save(update_fields=["verification_level"])

        with self.captureOnCommitCallbacks(execute=True):
            owner_save_product(
                self.owner,
                self.business,
                {"name": "Owned Item v2", "category": self.category},
                product=self.product,
            )

        self.product.refresh_from_db()
        self.assertEqual(
            self.product.verification_level, VerificationLevel.SOURCE_VERIFIED
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["root@example.com"])
        self.assertIn("Owned Item v2", mail.outbox[0].subject)
        self.assertIn(f"/admin/product/edit/{self.product.pk}/", mail.outbox[0].body)

    def test_owner_edit_of_other_levels_sends_no_reverification_email(self):
        get_user_model().objects.create_superuser("root", "root@example.com", "pass")
        with self.captureOnCommitCallbacks(execute=True):
            owner_save_product(
                self.owner,
                self.business,
                {"name": "Owned Item v2", "category": self.category},
                product=self.product,
            )
        self.assertEqual(len(mail.outbox), 0)

    def test_dashboard_shows_owner_listings(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertContains(response, 'id="my-listings"')
        self.assertContains(response, "Owned Item")
        self.assertContains(response, "Confirm everything is accurate")

    def test_dashboard_hides_owner_panel_for_non_owner(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertNotContains(response, 'id="my-listings"')

    # --- Customer reports --------------------------------------------------

    def test_report_emails_owner(self):
        self.client.post(
            reverse("reviews:report_product", args=[self.product.slug]),
            {"reason": ReportReason.PRICE_INCORRECT, "details": "Now $12"},
        )
        self.assertEqual(ProductReview.objects.filter(product=self.product).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["owner@example.com"])
        self.assertIn("Owned Item", mail.outbox[0].subject)

    # --- System monitors ---------------------------------------------------

    def test_monitor_sends_reminder_once_per_interval(self):
        out = StringIO()
        call_command("monitor_verification", stdout=out)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Owned Co", mail.outbox[0].subject)
        self.assertIn("Owned Item", mail.outbox[0].body)
        self.business.refresh_from_db()
        self.assertIsNotNone(self.business.verification_reminder_sent_at)

        call_command("monitor_verification", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)

    def test_monitor_dry_run_sends_nothing(self):
        out = StringIO()
        call_command("monitor_verification", "--dry-run", stdout=out)
        self.assertEqual(len(mail.outbox), 0)
        self.assertIn("Owners due for a reminder: 1", out.getvalue())

    def test_current_listings_not_due(self):
        self.business.verified_at = timezone.now()
        self.business.save()
        self.product.verified_at = timezone.now()
        self.product.save()
        self.assertEqual(businesses_due_for_reminder(), [])

    # --- Staff investigates exceptions -------------------------------------

    def _exception_for(self, obj, kind):
        for row in verification_exceptions():
            if row["kind"] == kind and row["obj"].pk == obj.pk:
                return row
        return None

    def test_no_owner_stale_business_is_exception(self):
        row = self._exception_for(self.orphan, "business")
        self.assertIsNotNone(row)
        self.assertIn("No manufacturer account", row["reasons"][0])

    def test_owned_due_business_without_reminder_is_not_exception(self):
        self.assertIsNone(self._exception_for(self.business, "business"))

    def test_unresponsive_owner_is_exception(self):
        self.business.verified_at = days_ago(200)
        self.business.verification_reminder_sent_at = days_ago(20)
        self.business.save()
        row = self._exception_for(self.business, "business")
        self.assertIsNotNone(row)
        self.assertIn("Owner reminded", row["reasons"][0])

    def test_owner_confirming_after_report_is_high_severity(self):
        report = ProductReview.objects.create(
            product=self.product,
            reason=ReportReason.PRODUCT_DISCONTINUED,
            status=ReportStatus.OPEN,
        )
        ProductReview.objects.filter(pk=report.pk).update(created_at=days_ago(2))
        self.client.force_login(self.owner)
        self.client.post(
            reverse("accounts:owner_confirm"),
            {"kind": "product", "business": self.business.pk, "pk": self.product.pk},
        )
        row = self._exception_for(self.product, "product")
        self.assertEqual(row["severity"], "high")

    def test_superuser_verify_records_source_and_clears_exception(self):
        superuser = get_user_model().objects.create_superuser(
            "root", "root@example.com", "pass"
        )
        BusinessReview.objects.create(
            business=self.orphan,
            reason=ReportReason.BUSINESS_CLOSED,
            status=ReportStatus.OPEN,
        )
        self.client.force_login(superuser)
        self.client.post(
            reverse("accounts:verify_listing"),
            {
                "kind": "business",
                "pk": self.orphan.pk,
                "level": VerificationLevel.SIMUDZA_VERIFIED,
            },
        )
        self.orphan.refresh_from_db()
        self.assertEqual(
            self.orphan.verification_level,
            VerificationLevel.SIMUDZA_VERIFIED,
        )
        self.assertEqual(self.orphan.verified_by, superuser)
        self.assertIsNone(self._exception_for(self.orphan, "business"))

    def test_staff_cannot_set_simudza_verified(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("accounts:verify_listing"),
            {
                "kind": "business",
                "pk": self.orphan.pk,
                "level": VerificationLevel.SIMUDZA_VERIFIED,
            },
            follow=True,
        )
        self.assertContains(response, "Only superusers can mark listings as Simudza Verified")
        self.orphan.refresh_from_db()
        self.assertEqual(self.orphan.verification_level, VerificationLevel.UNVERIFIED)

    def test_staff_level_choices_exclude_simudza_verified(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("accounts:dashboard"))
        levels = {meta.level for meta in response.context["verification_level_choices"]}
        self.assertNotIn(VerificationLevel.SIMUDZA_VERIFIED, levels)
        self.assertIn(VerificationLevel.SOURCE_VERIFIED, levels)

    def test_staff_set_verified_source_with_reference(self):
        self.client.force_login(self.staff)
        self.client.post(
            reverse("accounts:verify_listing"),
            {
                "kind": "product",
                "pk": self.product.pk,
                "level": VerificationLevel.SOURCE_VERIFIED,
                "reference": "ZimTrade registry #123",
            },
        )
        self.product.refresh_from_db()
        self.assertEqual(
            self.product.verification_level,
            VerificationLevel.SOURCE_VERIFIED,
        )
        self.assertEqual(
            self.product.verification_reference,
            "ZimTrade registry #123",
        )

    def test_discontinued_business_hidden_from_search(self):
        self.business.lifecycle_status = LifecycleStatus.DISCONTINUED
        self.business.verified_at = timezone.now()
        self.business.save()
        self.assertFalse(
            Business.objects.visible_in_search().filter(pk=self.business.pk).exists()
        )

    def test_trusted_levels_are_simudza_and_source_verified(self):
        self.assertEqual(
            TRUSTED_LEVELS,
            {VerificationLevel.SIMUDZA_VERIFIED, VerificationLevel.SOURCE_VERIFIED},
        )

    def test_trusted_levels_filter(self):
        self.business.verification_level = VerificationLevel.UNVERIFIED
        self.business.save(update_fields=["verification_level"])
        self.assertFalse(
            Business.objects.filter(
                pk=self.business.pk,
                verification_level__in=TRUSTED_LEVELS,
            ).exists()
        )
        self.business.verification_level = VerificationLevel.SIMUDZA_VERIFIED
        self.business.save(update_fields=["verification_level"])
        self.assertTrue(
            Business.objects.filter(
                pk=self.business.pk,
                verification_level__in=TRUSTED_LEVELS,
            ).exists()
        )

    def test_discontinued_excluded_from_exceptions(self):
        self.orphan.lifecycle_status = LifecycleStatus.DISCONTINUED
        self.orphan.save()
        self.assertIsNone(self._exception_for(self.orphan, "business"))

    def test_staff_dashboard_lists_exceptions(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertContains(response, "Exceptions to investigate")
        self.assertContains(response, "Orphan Co")
