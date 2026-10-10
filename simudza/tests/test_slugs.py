from unittest import mock

from django.db import IntegrityError
from django.test import TestCase

from businesses.models import Business, save_business_with_unique_slug
from categories.models import Category
from products.forms import save_product_with_unique_slug
from products.models import Product
from simudza.utils import slugs


def _stale_first_guess(stale_slug):
    """Simulate a concurrent writer: the first free-slug check is already out of date."""
    real = slugs.unique_slug
    calls = {"n": 0}

    def fake(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return stale_slug
        return real(*args, **kwargs)

    return mock.patch.object(slugs, "unique_slug", side_effect=fake)


class SaveWithUniqueSlugTests(TestCase):
    def test_business_retries_when_slug_claimed_concurrently(self):
        Business.objects.create(name="Acme Foods", slug="acme-foods")
        business = Business(name="Acme Foods")
        with _stale_first_guess("acme-foods"):
            save_business_with_unique_slug(business)
        self.assertEqual(business.slug, "acme-foods-2")
        self.assertTrue(Business.objects.filter(pk=business.pk).exists())
        self.assertEqual(Business.objects.count(), 2)

    def test_product_retries_when_slug_claimed_concurrently(self):
        business = Business.objects.create(name="Maker", slug="maker")
        category = Category.objects.create(name="Cat", slug="cat")
        Product.objects.create(
            business=business, category=category, name="Widget", slug="widget"
        )
        product = Product(business=business, category=category, name="Widget")
        with _stale_first_guess("widget"):
            save_product_with_unique_slug(product)
        self.assertEqual(product.slug, "widget-2")
        self.assertEqual(Product.objects.filter(name="Widget").count(), 2)

    def test_other_integrity_errors_are_not_swallowed(self):
        business = Business(name="Solo Co")

        def failing_save():
            raise IntegrityError("some other constraint")

        with self.assertRaises(IntegrityError):
            save_business_with_unique_slug(business, save=failing_save)
        self.assertFalse(Business.objects.filter(name="Solo Co").exists())

    def test_existing_record_keeps_its_own_slug(self):
        business = Business.objects.create(name="Same Name", slug="same-name")
        save_business_with_unique_slug(business)
        self.assertEqual(business.slug, "same-name")
