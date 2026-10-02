from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from django.urls import reverse

from businesses.models import Business
from businesses.verification import VerificationLevel
from businesses.verification_workflow import owner_confirm_products
from categories.models import Category
from history.context import change_context
from history.models import ChangeLog
from products.models import Product
from products.test_helpers import add_sellable_variant


class ChangeLogCaptureTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser("admin", "admin@x.com", "pass")
        self.business = Business.objects.create(name="Juice Co", slug="juice-co")
        self.category = Category.objects.create(name="Drinks", slug="drinks")
        self.product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="XYZ Juice",
            slug="xyz-juice",
        )
        self.variant = add_sellable_variant(
            self.product,
            price="2.50",
            sku="J-1",
        )

    def _save_with_commit(self, fn):
        with self.captureOnCommitCallbacks(execute=True):
            fn()

    def test_price_change_logs_old_and_new_values(self):
        self.variant.price = Decimal("2.80")
        with change_context(user=self.admin, source=ChangeLog.Source.ADMIN):
            self._save_with_commit(lambda: self.variant.save())

        row = ChangeLog.objects.for_object(self.variant).get(field_name="price")
        self.assertEqual(row.old_value, "$2.50")
        self.assertEqual(row.new_value, "$2.80")
        self.assertEqual(row.changed_by, self.admin)
        self.assertEqual(row.source, ChangeLog.Source.ADMIN)

    def test_create_and_delete_actions(self):
        with change_context(user=self.admin, source=ChangeLog.Source.ADMIN):
            self._save_with_commit(
                lambda: Category.objects.create(name="New Cat", slug="new-cat")
            )
        cat = Category.objects.get(slug="new-cat")
        self.assertTrue(
            ChangeLog.objects.for_object(cat).filter(action=ChangeLog.Action.CREATED).exists()
        )

        with change_context(user=self.admin):
            self._save_with_commit(lambda: cat.delete())
        self.assertTrue(
            ChangeLog.objects.filter(
                object_repr__icontains="New Cat",
                action=ChangeLog.Action.DELETED,
            ).exists()
        )

    def test_updated_at_never_logged(self):
        before = ChangeLog.objects.count()
        with change_context(user=self.admin):
            self._save_with_commit(lambda: self.business.save())
        self.assertFalse(
            ChangeLog.objects.filter(field_name="updated_at").exists()
        )
        self.assertEqual(ChangeLog.objects.count(), before)

    def test_owner_confirm_products_logs_verification(self):
        self.product.verification_level = VerificationLevel.UNVERIFIED
        self.product.save(update_fields=["verification_level"])
        User = get_user_model()
        owner = User.objects.create_user("owner", "owner@x.com", "pass")
        self.business.owner = owner
        self.business.save(update_fields=["owner"])

        with self.captureOnCommitCallbacks(execute=True):
            with change_context(user=owner, source=ChangeLog.Source.DASHBOARD):
                owner_confirm_products(self.business, owner)

        row = ChangeLog.objects.for_object(self.product).filter(
            field_name="verification_level"
        ).latest("changed_at")
        self.assertEqual(row.reason, "Owner confirmed listing")

    def test_rolled_back_save_writes_nothing(self):
        before = ChangeLog.objects.count()
        try:
            with self.captureOnCommitCallbacks(execute=True):
                with transaction.atomic():
                    self.variant.price = Decimal("9.99")
                    self.variant.save()
                    raise RuntimeError("rollback")
        except RuntimeError:
            pass
        self.assertEqual(ChangeLog.objects.count(), before)

    def test_admin_change_reason_on_product_edit(self):
        from django.test import Client

        client = Client()
        client.force_login(self.admin)
        url = reverse("product:edit", args=[self.product.pk])
        data = {
            "business": self.product.business_id,
            "name": self.product.name,
            "short_description": "",
            "description": "Updated story",
            "category": self.category.pk,
            "origin_type": self.product.origin_type,
            "brand_name": "",
            "status": self.product.status,
            "featured": "",
            "verified_at": "",
            "verification_level": self.product.verification_level,
            "verification_reference": "",
            "change_reason": "Corrected product description",
            "variants-TOTAL_FORMS": "1",
            "variants-INITIAL_FORMS": "1",
            "variants-MIN_NUM_FORMS": "1",
            "variants-MAX_NUM_FORMS": "1000",
            "variants-0-id": self.variant.pk,
            "variants-0-product": self.product.pk,
            "variants-0-name": "",
            "variants-0-size_value": "",
            "variants-0-size_unit": "",
            "variants-0-packaging": "",
            "variants-0-sku": self.variant.sku,
            "variants-0-barcode": "",
            "variants-0-price": str(self.variant.price),
            "variants-0-is_available": "on",
            "variants-0-ORDER": "1",
            "images-TOTAL_FORMS": "0",
            "images-INITIAL_FORMS": "0",
            "images-MIN_NUM_FORMS": "0",
            "images-MAX_NUM_FORMS": "1000",
            "videos-TOTAL_FORMS": "0",
            "videos-INITIAL_FORMS": "0",
            "videos-MIN_NUM_FORMS": "0",
            "videos-MAX_NUM_FORMS": "1000",
        }
        with self.captureOnCommitCallbacks(execute=True):
            response = client.post(url, data)
        self.assertEqual(response.status_code, 302, response.content[:1500])
        row = ChangeLog.objects.for_object(self.product).filter(
            field_name="description"
        ).latest("changed_at")
        self.assertEqual(row.reason, "Corrected product description")

    def test_change_history_admin_views(self):
        self.variant.price = Decimal("3.00")
        with change_context(user=self.admin, source=ChangeLog.Source.ADMIN):
            self._save_with_commit(lambda: self.variant.save())

        client = __import__("django.test", fromlist=["Client"]).Client()
        client.force_login(self.admin)
        list_url = reverse("change_log:index")
        response = client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "$3.00")

        edit_url = reverse("product_variant:edit", args=[self.variant.pk])
        response = client.get(edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "View all changes")
