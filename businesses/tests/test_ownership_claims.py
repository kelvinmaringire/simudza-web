from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from businesses.forms import OwnerCompanyForm, OwnerProductForm
from businesses.models import Business
from businesses.services import owner_save_company, owner_save_product
from businesses.verification.levels import VerificationLevel
from businesses.verification.workflow import (
    OwnershipNotConfirmed,
    confirm_ownership,
    owner_confirm_business,
    revoke_ownership,
    verification_exceptions,
)
from categories.models import Category
from products.models import Product


class OwnershipClaimTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.claimant = User.objects.create_user("claimant", "c@example.com", "pass")
        self.other = User.objects.create_user("other", "o@example.com", "pass")
        self.staff = User.objects.create_user(
            "staff", "s@example.com", "pass", is_staff=True
        )
        self.category = Category.objects.create(name="Cat", slug="cat")
        self.client = Client()

    def _register_company(self, name="Claimed Co"):
        form = OwnerCompanyForm(
            data={
                "name": name,
                "business_type": "manufacturer",
                "description": "",
                "website": "",
                "email": "",
                "phone": "",
                "address": "",
                "town_or_city": "",
            },
            user=self.claimant,
        )
        self.assertTrue(form.is_valid(), form.errors)
        return form.save()

    def _exception_for(self, business):
        for row in verification_exceptions():
            if row["kind"] == "business" and row["obj"].pk == business.pk:
                return row
        return None

    def test_new_company_is_created_inactive(self):
        business = self._register_company()
        self.assertFalse(business.is_active)
        self.assertFalse(Business.objects.served().filter(pk=business.pk).exists())

    def test_new_company_is_created_unverified_with_unconfirmed_owner(self):
        business = self._register_company()
        self.assertEqual(business.owner, self.claimant)
        self.assertFalse(business.owner_is_confirmed)
        self.assertEqual(business.verification_level, VerificationLevel.UNVERIFIED)
        self.assertIsNone(business.verified_at)
        self.assertNotIn(business, Business.objects.visible_in_search())

    def test_unconfirmed_owner_cannot_self_verify(self):
        business = self._register_company()
        with self.assertRaises(OwnershipNotConfirmed):
            owner_confirm_business(business, self.claimant)

        self.client.force_login(self.claimant)
        response = self.client.post(
            reverse("accounts:owner_confirm"),
            {"kind": "all", "business": business.pk},
        )
        self.assertEqual(response.status_code, 302)
        business.refresh_from_db()
        self.assertEqual(business.verification_level, VerificationLevel.UNVERIFIED)
        self.assertIsNone(business.verified_at)

    def test_dashboard_hides_confirm_buttons_until_ownership_confirmed(self):
        business = self._register_company()
        self.client.force_login(self.claimant)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertContains(response, "Simudza is confirming that you represent")
        self.assertNotContains(response, "Confirm everything is accurate")

        confirm_ownership(business, self.staff)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertContains(response, "Confirm everything is accurate")

    def test_unconfirmed_owner_new_product_is_not_verified(self):
        business = self._register_company()
        product = owner_save_product(
            self.claimant,
            business,
            {
                "name": "Claimed Product",
                "category": self.category,
                "origin_type": Product.OriginType.MADE_IN_ZIMBABWE,
            },
        )
        self.assertEqual(product.verification_level, VerificationLevel.UNVERIFIED)
        self.assertIsNone(product.verified_at)

    def test_unconfirmed_owner_edit_drops_trusted_level(self):
        business = self._register_company()
        product = Product.objects.create(
            business=business,
            category=self.category,
            name="Checked",
            slug="checked",
            verification_level=VerificationLevel.SIMUDZA_VERIFIED,
            verified_at=timezone.now(),
        )
        owner_save_product(
            self.claimant,
            business,
            {"name": "Checked v2", "category": self.category},
            product=product,
        )
        product.refresh_from_db()
        self.assertEqual(product.name, "Checked v2")
        self.assertEqual(
            product.verification_level, VerificationLevel.COMMUNITY_REPORTED
        )

    def test_confirmed_owner_confirmation_is_source_checked_not_simudza_verified(self):
        business = self._register_company()
        confirm_ownership(business, self.staff)
        owner_confirm_business(business, self.claimant)
        business.refresh_from_db()
        self.assertEqual(
            business.verification_level, VerificationLevel.SOURCE_VERIFIED
        )
        self.assertIsNotNone(business.verified_at)

    def test_reassigning_owner_invalidates_confirmation(self):
        business = self._register_company()
        confirm_ownership(business, self.staff)
        business.owner = self.other
        business.save()
        business.refresh_from_db()
        self.assertFalse(business.owner_is_confirmed)
        with self.assertRaises(OwnershipNotConfirmed):
            owner_confirm_business(business, self.other)

    def test_pending_claim_is_staff_exception_until_confirmed(self):
        business = self._register_company()
        row = self._exception_for(business)
        self.assertIsNotNone(row)
        self.assertIn("awaits staff confirmation", " ".join(row["reasons"]))

        confirm_ownership(business, self.staff)
        row = self._exception_for(business)
        self.assertTrue(
            row is None
            or not any("awaits staff confirmation" in r for r in row["reasons"])
        )

        revoke_ownership(business, self.staff)
        self.assertIsNotNone(self._exception_for(business))


class OwnerWritePermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user("owner", "o@example.com", "pass")
        self.other = User.objects.create_user("other", "x@example.com", "pass")
        self.category = Category.objects.create(name="Cat", slug="cat")
        self.business = Business.objects.create(
            name="Owned Co",
            slug="owned-co",
            owner=self.owner,
        )
        self.client = Client()

    def test_non_owner_cannot_edit_company_via_view(self):
        self.client.force_login(self.other)
        response = self.client.get(
            reverse("businesses:submit_company_update", kwargs={"pk": self.business.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_non_owner_cannot_save_company_via_service(self):
        with self.assertRaises(PermissionError):
            owner_save_company(
                self.other,
                {"name": "Hijacked", "business_type": "manufacturer"},
                business=self.business,
            )

    def test_non_owner_cannot_edit_product_via_view(self):
        product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="P",
            slug="p",
        )
        self.client.force_login(self.other)
        response = self.client.get(
            reverse(
                "businesses:submit_product_update",
                kwargs={"product_id": product.pk},
            )
        )
        self.assertEqual(response.status_code, 404)
