from django.test import TestCase

from businesses.models import Business
from businesses.verification.levels import VerificationLevel
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


class NewListingNotVerifiedTests(TestCase):
    def test_new_business_has_no_verified_at_and_is_hidden(self):
        business = Business.objects.create(name="New Co", slug="new-co")
        self.assertIsNone(business.verified_at)
        self.assertNotIn(business, Business.objects.visible_in_search())

    def test_new_product_under_verified_business_is_hidden(self):
        business = Business.objects.create(name="Co", slug="co")
        business.verified_at = business.created_at
        business.save(update_fields=["verified_at"])
        category = Category.objects.create(name="C", slug="c")
        product = Product.objects.create(
            business=business,
            category=category,
            name="P",
            slug="p",
        )
        self.assertIsNone(product.verified_at)
        self.assertNotIn(product, Product.objects.visible_in_search())
