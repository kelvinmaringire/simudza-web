from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse

from businesses.models import Business
from businesses.verification import VerificationLevel
from businesses.verification_workflow import bulk_set_level
from categories.models import Category
from history.models import ChangeLog
from products.models import Product
from simudza.utils.bulk_edit import (
    BulkEditValidationError,
    apply_bulk_changes,
    preview_bulk_changes,
    validate_category_parent_bulk,
)


class BulkEditDomainTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_superuser("staff", "staff@example.com", "pass")
        self.business = Business.objects.create(name="Biz", slug="biz")
        self.category = Category.objects.create(name="Cat", slug="cat")
        self.other_category = Category.objects.create(name="Other", slug="other-cat")

    def _product(self, name, **kwargs):
        return Product.objects.create(
            business=self.business,
            category=self.category,
            name=name,
            slug=name.lower().replace(" ", "-"),
            **kwargs,
        )

    def test_preview_and_apply_featured(self):
        p1 = self._product("One", featured=False)
        p2 = self._product("Two", featured=False)
        values = {"featured": True}
        rows, unchanged = preview_bulk_changes([p1, p2], values)
        self.assertEqual(len(rows), 2)
        self.assertEqual(unchanged, 0)

        with self.captureOnCommitCallbacks(execute=True):
            updated, unchanged_after = apply_bulk_changes(
                [p1, p2],
                values,
                user=self.staff,
                reason="Test bulk featured",
            )
        self.assertEqual(updated, 2)
        self.assertEqual(unchanged_after, 0)
        p1.refresh_from_db()
        self.assertTrue(p1.featured)
        self.assertTrue(
            ChangeLog.objects.filter(
                object_id=str(p1.pk),
                source=ChangeLog.Source.BULK_EDIT,
                reason="Test bulk featured",
            ).exists()
        )

    def test_apply_skips_unchanged(self):
        p1 = self._product("Same", featured=True)
        updated, unchanged = apply_bulk_changes(
            [p1],
            {"featured": True},
            user=self.staff,
            reason="No-op",
        )
        self.assertEqual(updated, 0)
        self.assertEqual(unchanged, 1)

    def test_category_parent_cannot_be_selected(self):
        parent = Category.objects.create(name="Parent", slug="parent-cat")
        child = Category.objects.create(name="Child", slug="child-cat", parent=parent)
        with self.assertRaises(BulkEditValidationError):
            validate_category_parent_bulk([parent, child], parent)

    def test_bulk_set_level(self):
        business = Business.objects.create(name="V Biz", slug="v-biz")
        bulk_set_level(
            [business],
            self.staff,
            VerificationLevel.SIMUDZA_CHECKED,
            reference="ref-1",
        )
        business.refresh_from_db()
        self.assertEqual(business.verification_level, VerificationLevel.SIMUDZA_CHECKED)
        self.assertEqual(business.verification_reference, "ref-1")


class BulkEditAdminViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_superuser("admin", "admin@example.com", "pass")
        self.viewer = User.objects.create_user(
            "viewer",
            "viewer@example.com",
            "pass",
            is_staff=True,
        )
        view_perm = Permission.objects.get(
            codename="view_product",
            content_type=ContentType.objects.get_for_model(Product),
        )
        self.viewer.user_permissions.add(view_perm)
        self.business = Business.objects.create(name="Co", slug="co")
        self.category = Category.objects.create(name="Food", slug="food")
        self.products = [
            Product.objects.create(
                business=self.business,
                category=self.category,
                name=f"Product {i}",
                slug=f"product-{i}",
                featured=False,
            )
            for i in range(3)
        ]
        self.client = Client()
        self.admin_host = {"HTTP_HOST": "localhost"}

    def _bulk_url(self, *pks):
        base = reverse(
            "wagtail_bulk_action",
            kwargs={
                "app_label": "products",
                "model_name": "product",
                "action": "bulk_edit",
            },
        )
        ids = "&".join(f"id={pk}" for pk in pks)
        return f"{base}?{ids}&next=/admin/products/"

    def test_preview_then_confirm_updates_products(self):
        pks = [p.pk for p in self.products]
        url = self._bulk_url(*pks)
        self.client.force_login(self.staff)

        get_resp = self.client.get(url, **self.admin_host)
        self.assertEqual(get_resp.status_code, 200)

        preview_post = {
            "change_reason": "Mark featured",
            "change_featured": "on",
            "featured": "on",
        }
        preview_resp = self.client.post(url, preview_post, **self.admin_host)
        self.assertEqual(preview_resp.status_code, 200)
        self.assertContains(preview_resp, "Confirm bulk edit")
        self.assertContains(preview_resp, "Apply changes")

        confirm_post = {**preview_post, "confirm": "1"}
        with self.captureOnCommitCallbacks(execute=True):
            confirm_resp = self.client.post(url, confirm_post, **self.admin_host)
        self.assertEqual(confirm_resp.status_code, 302)

        for product in self.products:
            product.refresh_from_db()
            self.assertTrue(product.featured)

        self.assertTrue(
            ChangeLog.objects.filter(
                object_id=str(self.products[0].pk),
                source=ChangeLog.Source.BULK_EDIT,
                reason="Mark featured",
            ).exists()
        )

    def test_viewer_without_change_permission_cannot_update(self):
        url = self._bulk_url(self.products[0].pk)
        self.client.force_login(self.viewer)
        post = {
            "change_reason": "Should not apply",
            "change_featured": "on",
            "featured": "on",
            "confirm": "1",
        }
        self.client.post(url, post, **self.admin_host)
        self.products[0].refresh_from_db()
        self.assertFalse(self.products[0].featured)

    def test_product_index_has_bulk_checkboxes(self):
        self.client.force_login(self.staff)
        index_url = reverse("product:index")
        response = self.client.get(index_url, **self.admin_host)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bulk-actions.js")
        self.assertContains(response, "bulk-action-checkbox")
