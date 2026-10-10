from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from categories.models import Category


class CategoryTreePathTests(TestCase):
    def setUp(self):
        self.food = Category.objects.create(name="Food", slug="food")
        self.beverages = Category.objects.create(
            name="Beverages", slug="beverages", parent=self.food
        )
        self.tea = Category.objects.create(
            name="Tea", slug="tea", parent=self.beverages
        )
        self.apparel = Category.objects.create(name="Apparel", slug="apparel")

    def test_annotates_root_first_path(self):
        tea = Category.objects.with_tree_path().get(pk=self.tea.pk)
        self.assertEqual(tea.tree_path_names, ["Food", "Beverages", "Tea"])
        self.assertEqual(
            tea.tree_path_ids, [self.food.pk, self.beverages.pk, self.tea.pk]
        )

    def test_ordering_groups_children_under_parents(self):
        names = [
            c.name
            for c in Category.objects.with_tree_path().order_by("tree_path_names")
        ]
        self.assertEqual(names, ["Apparel", "Food", "Beverages", "Tea"])

    def test_path_terminates_on_existing_cycle(self):
        Category.objects.filter(pk=self.food.pk).update(parent=self.tea)
        tea = Category.objects.with_tree_path().get(pk=self.tea.pk)
        self.assertEqual(tea.tree_path_names, ["Food", "Beverages", "Tea"])


class CategoryAdminTreeListTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_superuser("admin", "a@example.com", "pass")
        self.food = Category.objects.create(name="Food", slug="food")
        self.beverages = Category.objects.create(
            name="Beverages", slug="beverages", parent=self.food
        )
        self.tea = Category.objects.create(
            name="Tea", slug="tea", parent=self.beverages
        )
        self.client.force_login(self.staff)

    def test_index_links_every_level(self):
        response = self.client.get(reverse("category:index"), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        for category in (self.food, self.beverages, self.tea):
            self.assertContains(
                response, reverse("category:edit", args=[category.pk])
            )
        content = response.content.decode()
        food_url, beverages_url, tea_url = (
            reverse("category:edit", args=[c.pk])
            for c in (self.food, self.beverages, self.tea)
        )
        # Tea's row is last and renders the whole path as links.
        self.assertLess(content.rindex(f'"{food_url}"'), content.rindex(f'"{beverages_url}"'))
        self.assertLess(content.rindex(f'"{beverages_url}"'), content.rindex(f'"{tea_url}"'))

    def _count_index_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(reverse("category:index"), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        return len(ctx.captured_queries)

    def test_index_query_count_does_not_grow_with_categories(self):
        baseline = self._count_index_queries()
        for i in range(10):
            Category.objects.create(name=f"Sub {i}", slug=f"sub-{i}", parent=self.food)
        self.assertEqual(self._count_index_queries(), baseline)

    def test_index_sortable_by_attention(self):
        response = self.client.get(
            reverse("category:index"),
            {"ordering": "-attention_count"},
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 200)

    def test_index_sortable_by_path_descending(self):
        response = self.client.get(
            reverse("category:index"),
            {"ordering": "-tree_path_names"},
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 200)
