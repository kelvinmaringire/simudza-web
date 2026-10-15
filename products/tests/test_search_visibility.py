from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from businesses.models import Business
from businesses.verification.levels import FreshnessTier
from categories.models import Category
from products.models import Product


class ProductVisibleInSearchTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user("vis", "vis@x.com", "pass")
        self.category = Category.objects.create(name="Vis", slug="vis")
        self.business = Business.objects.create(
            name="Vis Biz",
            slug="vis-biz",
            owner=owner,
            verified_at=timezone.now(),
        )

    def test_visible_in_search_excludes_hidden_by_age(self):
        fresh = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Fresh",
            slug="fresh-vis",
            verified_at=timezone.now(),
        )
        hidden = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Hidden",
            slug="hidden-vis",
            verified_at=timezone.now() - timedelta(days=366),
        )
        visible_ids = set(Product.objects.visible_in_search().values_list("pk", flat=True))
        self.assertIn(fresh.pk, visible_ids)
        self.assertNotIn(hidden.pk, visible_ids)
        self.assertEqual(hidden.freshness.tier, FreshnessTier.HIDDEN)
