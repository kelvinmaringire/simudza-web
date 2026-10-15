from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import Client, TestCase
from django.urls import reverse

from businesses.models import Business
from businesses.verification.levels import VerificationLevel
from businesses.verification.workflow import owner_confirm_products
from categories.models import Category
from history.backfill import backfill_raw_values
from history.context import change_context
from history.models import ChangeLog
from history.undo import UndoError, batch_entries, undo_blocker, undo_entries
from marketplace.test_helpers import add_sellable_variant
from products.models import Product


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
        self.offer = self.variant.offer

    def _save_with_commit(self, fn):
        with self.captureOnCommitCallbacks(execute=True):
            fn()

    def test_price_change_logs_old_and_new_values(self):
        self.offer.price = Decimal("2.80")
        with change_context(user=self.admin, source=ChangeLog.Source.ADMIN):
            self._save_with_commit(lambda: self.offer.save())

        row = ChangeLog.objects.for_object(self.offer).get(field_name="price")
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
        self.business.confirmed_owner = owner
        self.business.save(update_fields=["owner", "confirmed_owner"])

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
                    self.offer.price = Decimal("9.99")
                    self.offer.save()
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
            "variants-0-ORDER": "1",
            "variants-0-images-TOTAL_FORMS": "0",
            "variants-0-images-INITIAL_FORMS": "0",
            "variants-0-images-MIN_NUM_FORMS": "0",
            "variants-0-images-MAX_NUM_FORMS": "1000",
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
        self.offer.price = Decimal("3.00")
        with change_context(user=self.admin, source=ChangeLog.Source.ADMIN):
            self._save_with_commit(lambda: self.offer.save())

        client = __import__("django.test", fromlist=["Client"]).Client()
        client.force_login(self.admin)
        list_url = reverse("change_log:index")
        response = client.get(list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "$3.00")

        edit_url = reverse("variant_offer:edit", args=[self.offer.pk])
        response = client.get(edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "View all changes")

    def test_change_log_listing_shows_field_and_values(self):
        self.offer.price = Decimal("4.00")
        with change_context(user=self.admin, source=ChangeLog.Source.ADMIN):
            self._save_with_commit(lambda: self.offer.save())

        client = __import__("django.test", fromlist=["Client"]).Client()
        client.force_login(self.admin)
        response = client.get(reverse("change_log:index"))
        for text in ("Action", "Field", "Old value", "New value", "Updated", "$4.00"):
            self.assertContains(response, text)

    def test_deletion_entry_displays_record_and_deleted(self):
        entry = ChangeLog(
            content_type_id=1,
            object_id="1",
            object_repr="Mazoe Raspberry",
            action=ChangeLog.Action.DELETED,
        )
        self.assertEqual(entry.field_display, "Whole record")
        self.assertEqual(entry.old_value_display, "Mazoe Raspberry")
        self.assertEqual(entry.new_value_display, "Deleted")


class ChangeLogUndoTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser("admin", "admin@x.com", "pass")
        self.business = Business.objects.create(name="Juice Co", slug="juice-co")
        self.category = Category.objects.create(name="Drinks", slug="drinks")
        self.other_category = Category.objects.create(name="Snacks", slug="snacks")
        self.product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="XYZ Juice",
            slug="xyz-juice",
        )
        self.offer = add_sellable_variant(self.product, price="2.50", sku="J-1").offer

    def _edit_product(self, **values):
        for name, value in values.items():
            setattr(self.product, name, value)
        with self.captureOnCommitCallbacks(execute=True):
            with change_context(user=self.admin, source=ChangeLog.Source.ADMIN):
                self.product.save()

    def _entry(self, field_name, obj=None):
        return ChangeLog.objects.for_object(obj or self.product).filter(
            field_name=field_name
        ).latest("pk")

    def _undo(self, entries):
        with self.captureOnCommitCallbacks(execute=True):
            return undo_entries(entries, user=self.admin)

    def test_update_stores_raw_values(self):
        self._edit_product(category=self.other_category)
        entry = self._entry("category")
        self.assertTrue(entry.raw_captured)
        self.assertEqual(entry.old_raw, self.category.pk)
        self.assertEqual(entry.new_raw, self.other_category.pk)

    def test_undo_single_field_restores_value_and_logs_undo(self):
        self._edit_product(name="New Name", category=self.other_category)
        original = self._entry("name")
        self._undo([original])

        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "XYZ Juice")
        self.assertEqual(self.product.category, self.other_category)
        original.refresh_from_db()
        self.assertIsNotNone(original.undone_at)
        self.assertEqual(original.undone_by, self.admin)
        undo_row = self._entry("name")
        self.assertEqual(undo_row.source, ChangeLog.Source.UNDO)
        self.assertEqual(undo_row.new_value, "XYZ Juice")

    def test_undo_decimal_field(self):
        self.offer.price = Decimal("3.10")
        with self.captureOnCommitCallbacks(execute=True):
            self.offer.save()
        self._undo([self._entry("price", self.offer)])
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.price, Decimal("2.50"))

    def test_undo_whole_save(self):
        self._edit_product(name="New Name", category=self.other_category)
        entry = self._entry("name")
        batch = batch_entries(entry)
        self.assertEqual(len(batch), 2)

        self.assertEqual(self._undo(batch), 2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "XYZ Juice")
        self.assertEqual(self.product.category, self.category)

    def test_changed_since_blocks_undo(self):
        self._edit_product(name="Second")
        first = self._entry("name")
        self._edit_product(name="Third")

        self.assertIn("changed since", undo_blocker(first))
        with self.assertRaises(UndoError):
            self._undo([first])
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Third")

    def test_already_undone_and_legacy_entries_blocked(self):
        self._edit_product(name="Second")
        entry = self._entry("name")
        self._undo([entry])
        entry.refresh_from_db()
        self.assertEqual(undo_blocker(entry), "Already undone.")

        self._edit_product(name="Fourth")
        legacy = self._entry("name")
        ChangeLog.objects.filter(pk=legacy.pk).update(raw_captured=False)
        legacy.refresh_from_db()
        self.assertFalse(legacy.may_be_undoable)
        self.assertEqual(undo_blocker(legacy), "Recorded before undo was available.")

    def test_backfill_makes_legacy_updates_undoable(self):
        self._edit_product(name="Renamed", category=self.other_category)
        ChangeLog.objects.update(raw_captured=False, old_raw=None, new_raw=None)

        backfill_raw_values()
        name_entry = self._entry("name")
        category_entry = self._entry("category")
        self.assertEqual((name_entry.old_raw, name_entry.new_raw), ("XYZ Juice", "Renamed"))
        self.assertEqual(category_entry.old_raw, self.category.pk)

        self._undo(batch_entries(name_entry))
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "XYZ Juice")
        self.assertEqual(self.product.category, self.category)

    def test_edit_url_redirects_to_inspect(self):
        self._edit_product(name="Renamed")
        entry = self._entry("name")
        client = Client()
        client.force_login(self.admin)
        response = client.get(reverse("change_log:edit", args=[entry.pk]))
        self.assertRedirects(response, reverse("change_log:inspect", args=[entry.pk]))

    def test_verification_fields_not_undoable(self):
        entry = ChangeLog(
            content_type_id=1,
            object_id="1",
            action=ChangeLog.Action.UPDATED,
            field_name="verification_level",
            raw_captured=True,
        )
        self.assertIn("verification workflow", undo_blocker(entry))

    def test_admin_undo_page_and_post(self):
        self._edit_product(name="New Name", category=self.other_category)
        entry = self._entry("name")
        client = Client()
        client.force_login(self.admin)

        self.assertContains(client.get(reverse("change_log:index")), reverse("change_log:undo", args=[entry.pk]))
        self.assertContains(client.get(reverse("change_log:inspect", args=[entry.pk])), "Undo")
        page = client.get(reverse("change_log:undo", args=[entry.pk]))
        self.assertContains(page, "Undo this change")
        self.assertContains(page, "Undo all 2 changes made together")

        with self.captureOnCommitCallbacks(execute=True):
            response = client.post(
                reverse("change_log:undo", args=[entry.pk]), {"scope": "batch"}
            )
        self.assertRedirects(response, reverse("change_log:inspect", args=[entry.pk]))
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "XYZ Juice")
        self.assertEqual(self.product.category, self.category)
