from django.contrib.auth import get_user_model
from django.test import TestCase

from businesses.models import Business
from categories.models import Category
from directory.models import DirectoryListing
from products.models import Product


class DirectoryListingSignalTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user("dir", "dir@x.com", "pass")
        self.category = Category.objects.create(name="Dir Cat", slug="dir-cat")
        self.business = Business.objects.create(
            name="Dir Biz",
            slug="dir-biz",
            owner=owner,
        )

    def test_product_create_auto_creates_directory_listing(self):
        product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Auto Listed",
            slug="auto-listed",
        )
        listing = DirectoryListing.objects.get(product=product)
        self.assertFalse(listing.featured)
        self.assertTrue(listing.show_in_directory)

    def test_product_save_heals_missing_directory_listing(self):
        product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Heal Me",
            slug="heal-me",
        )
        DirectoryListing.objects.filter(product=product).delete()
        self.assertFalse(DirectoryListing.objects.filter(product=product).exists())

        product.name = "Healed"
        product.save()

        self.assertTrue(DirectoryListing.objects.filter(product=product).exists())
