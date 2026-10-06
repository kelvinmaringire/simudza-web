import tablib
from django.test import TestCase

from categories.models import Category
from categories.resources import CategoryResource

EXPECTED_HEADERS = [
    "id",
    "name",
    "slug",
    "parent",
    "is_active",
    "created_at",
    "updated_at",
]


class CategoryResourceTests(TestCase):
    def setUp(self):
        self.food = Category.objects.create(name="Food", slug="food")
        self.tea = Category.objects.create(name="Tea", slug="tea", parent=self.food)

    def test_export_includes_every_column(self):
        dataset = CategoryResource().export()
        self.assertEqual(dataset.headers, EXPECTED_HEADERS)
        row = next(r for r in dataset.dict if r["slug"] == "tea")
        self.assertEqual(row["id"], str(self.tea.pk))
        self.assertEqual(row["name"], "Tea")
        self.assertEqual(row["parent"], "food")

    def test_export_reimports_without_changes(self):
        result = CategoryResource().import_data(CategoryResource().export(), dry_run=True)
        self.assertFalse(result.has_errors())
        self.assertFalse(result.has_validation_errors())
        self.assertEqual(result.totals["skip"], 2)

    def test_import_matches_on_slug_and_ignores_readonly_columns(self):
        created_at = self.tea.created_at
        dataset = tablib.Dataset(headers=EXPECTED_HEADERS)
        dataset.append(
            [99999, "Green tea", "tea", "food", "1", "2000-01-01 00:00:00", ""]
        )
        result = CategoryResource().import_data(dataset)
        self.assertFalse(result.has_errors())
        self.assertFalse(result.has_validation_errors())

        self.assertEqual(Category.objects.count(), 2)
        self.tea.refresh_from_db()
        self.assertEqual(self.tea.name, "Green tea")
        self.assertEqual(self.tea.created_at, created_at)
        self.assertFalse(Category.objects.filter(pk=99999).exists())

    def test_import_creates_new_category_by_slug(self):
        dataset = tablib.Dataset(headers=["name", "slug", "parent", "is_active"])
        dataset.append(["Coffee", "coffee", "food", "1"])
        result = CategoryResource().import_data(dataset)
        self.assertFalse(result.has_errors())
        coffee = Category.objects.get(slug="coffee")
        self.assertEqual(coffee.parent, self.food)
