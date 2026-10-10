from django.test import TestCase

from businesses.models import Business
from categories.models import Category
from categories.quality import category_issues, issue_counts, needing_attention_count
from products.models import Product


class CategoryNoPublishedProductsTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="Maker", slug="maker")
        self.food = Category.objects.create(name="Food", slug="food")
        self.beverages = Category.objects.create(
            name="Beverages", slug="beverages", parent=self.food
        )
        self.tea = Category.objects.create(
            name="Tea", slug="tea", parent=self.beverages
        )
        Product.objects.create(
            business=self.business,
            category=self.tea,
            name="Rooibos",
            slug="rooibos",
            status=Product.ProductStatus.PUBLISHED,
        )

    def test_top_level_category_without_products_is_not_flagged(self):
        self.assertEqual(category_issues(self.food), [])

    def test_child_category_without_published_products_is_flagged(self):
        self.assertEqual(category_issues(self.beverages), ["no_published_products"])

    def test_child_category_with_published_products_is_not_flagged(self):
        self.assertEqual(category_issues(self.tea), [])

    def test_counts_exclude_top_level_categories(self):
        self.assertEqual(issue_counts()["no_published_products"], 1)
        self.assertEqual(needing_attention_count(), 1)
        self.assertQuerySetEqual(
            Category.objects.needing_attention(), [self.beverages]
        )

    def test_with_attention_matches_issue_rules(self):
        self.food.is_active = False
        self.food.save()
        Product.objects.create(
            business=self.business, category=self.food, name="Hamper", slug="hamper"
        )
        rows = {c.slug: c for c in Category.objects.with_attention()}
        for slug, category in rows.items():
            self.assertEqual(
                category.attention_count,
                len(category_issues(Category.objects.get(slug=slug))),
                slug,
            )
        self.assertEqual(rows["food"].attention_count, 1)
        self.assertTrue(rows["food"].issue_inactive_with_products)
        self.assertEqual(rows["beverages"].attention_count, 1)
        self.assertTrue(rows["beverages"].issue_no_published_products)
        self.assertEqual(rows["tea"].attention_count, 0)

    def test_category_issues_reuses_loaded_flags(self):
        beverages = Category.objects.with_attention().get(pk=self.beverages.pk)
        with self.assertNumQueries(0):
            self.assertEqual(category_issues(beverages), ["no_published_products"])

    def test_inactive_top_level_with_products_is_still_flagged(self):
        Product.objects.create(
            business=self.business,
            category=self.food,
            name="Mixed hamper",
            slug="mixed-hamper",
        )
        self.food.is_active = False
        self.food.save()
        self.assertEqual(category_issues(self.food), ["inactive_with_products"])
