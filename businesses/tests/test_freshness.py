from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from businesses.models import Business
from businesses.verification.levels import FreshnessTier, freshness_for
from categories.models import Category
from products.models import Product


class FreshnessTierTests(TestCase):
    def setUp(self):
        self.now = timezone.now()

    def test_freshness_tier_boundaries(self):
        cases = [
            (0, FreshnessTier.CURRENT),
            (90, FreshnessTier.CURRENT),
            (91, FreshnessTier.NEEDS),
            (180, FreshnessTier.NEEDS),
            (181, FreshnessTier.STALE),
            (365, FreshnessTier.STALE),
            (366, FreshnessTier.HIDDEN),
            (None, FreshnessTier.HIDDEN),
        ]
        for days, expected in cases:
            with self.subTest(days=days):
                dt = None if days is None else self.now - timedelta(days=days)
                self.assertEqual(freshness_for(dt, now=self.now).tier, expected)


class ProductEffectiveVerificationTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user("o", "o@x.com", "pass")
        self.category = Category.objects.create(name="C", slug="c")
        self.business = Business.objects.create(
            name="Biz",
            slug="biz",
            owner=owner,
            verified_at=timezone.now() - timedelta(days=200),
        )

    def test_effective_verified_at_uses_older_business_date(self):
        product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="P",
            slug="p",
            verified_at=timezone.now(),
        )
        self.assertEqual(product.effective_verified_at, self.business.verified_at)
        self.assertEqual(product.freshness.tier, FreshnessTier.STALE)
