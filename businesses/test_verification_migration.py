from django.test import TestCase

from businesses.models import Business
from businesses.verification import VerificationLevel
from products.models import Product
from categories.models import Category


class VerificationLevelMigrationMappingTests(TestCase):
    """Documents expected level values after 0009/0017 data migration."""

    def test_default_new_listing_is_unverified(self):
        business = Business.objects.create(name="New Co", slug="new-co")
        self.assertEqual(
            business.verification_level,
            VerificationLevel.UNVERIFIED,
        )

    def test_product_default_is_unverified(self):
        business = Business.objects.create(name="Co", slug="co")
        category = Category.objects.create(name="C", slug="c")
        product = Product.objects.create(
            business=business,
            category=category,
            name="P",
            slug="p",
        )
        self.assertEqual(
            product.verification_level,
            VerificationLevel.UNVERIFIED,
        )
