import tablib
from django.core.exceptions import ValidationError
from django.test import TestCase

from categories.forms import CategoryForm
from categories.models import Category
from categories.resources import CategoryResource


class CategoryHierarchyTests(TestCase):
    def setUp(self):
        self.food = Category.objects.create(name="Food", slug="food")
        self.beverages = Category.objects.create(
            name="Beverages", slug="beverages", parent=self.food
        )
        self.tea = Category.objects.create(
            name="Tea", slug="tea", parent=self.beverages
        )

    def test_self_parent_rejected(self):
        self.tea.parent = self.tea
        with self.assertRaises(ValidationError) as ctx:
            self.tea.full_clean()
        self.assertIn("parent", ctx.exception.message_dict)

    def test_direct_cycle_rejected(self):
        self.food.parent = self.beverages
        with self.assertRaises(ValidationError) as ctx:
            self.food.full_clean()
        self.assertIn("parent", ctx.exception.message_dict)

    def test_deep_cycle_rejected(self):
        self.food.parent = self.tea
        with self.assertRaises(ValidationError):
            self.food.full_clean()

    def test_valid_reparent_allowed(self):
        drinks = Category.objects.create(name="Drinks", slug="drinks")
        self.tea.parent = drinks
        self.tea.full_clean()

    def test_new_category_with_parent_allowed(self):
        Category(name="Coffee", slug="coffee", parent=self.beverages).full_clean()

    def test_str_shows_full_path(self):
        self.assertEqual(str(self.tea), "Food → Beverages → Tea")

    def test_str_terminates_on_existing_cycle(self):
        Category.objects.filter(pk=self.food.pk).update(parent=self.tea)
        tea = Category.objects.get(pk=self.tea.pk)
        self.assertEqual(str(tea), "Food → Beverages → Tea")

    def test_admin_form_rejects_cycle(self):
        form = CategoryForm(
            data={"name": "Food", "parent": self.tea.pk, "is_active": "on"},
            instance=self.food,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("parent", form.errors)

    def test_import_rejects_cycle(self):
        dataset = tablib.Dataset(headers=["slug", "name", "parent", "is_active"])
        dataset.append(["food", "Food", "tea", "1"])
        result = CategoryResource().import_data(dataset, dry_run=True)
        self.assertTrue(result.has_validation_errors())
        self.food.refresh_from_db()
        self.assertIsNone(self.food.parent_id)
