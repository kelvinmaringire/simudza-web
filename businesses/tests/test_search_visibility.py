from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from businesses.models import Business
from businesses.verification.levels import FreshnessTier, LifecycleStatus, VerificationLevel
from categories.models import Category
from directory.models import DirectoryListing
from products.models import Product
from products.test_helpers import add_sellable_variant


class SearchVisibilityTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(
            "owner",
            "owner@example.com",
            "pass",
        )
        self.category = Category.objects.create(name="Cat", slug="cat")
        self.business = Business.objects.create(
            name="Fresh Co",
            slug="fresh-co",
            owner=owner,
            verified_at=timezone.now(),
        )
        self.hidden_business = Business.objects.create(
            name="Stale Co",
            slug="stale-co",
            owner=owner,
            verified_at=timezone.now() - timedelta(days=400),
        )
        self.product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Fresh Item",
            slug="fresh-item",
            verified_at=timezone.now(),
        )
        add_sellable_variant(self.product, price="10.00")
        self.hidden_product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Old Item",
            slug="old-item",
            verified_at=timezone.now() - timedelta(days=400),
        )
        add_sellable_variant(self.hidden_product, price="12.00")
        self.inherited_product = Product.objects.create(
            business=self.hidden_business,
            category=self.category,
            name="Inherited Stale",
            slug="inherited-stale",
            verified_at=timezone.now(),
        )
        add_sellable_variant(self.inherited_product, price="15.00")
        for product in (self.product, self.hidden_product, self.inherited_product):
            DirectoryListing.objects.get_or_create(product=product)

    def test_business_visible_in_search_excludes_stale(self):
        visible = set(Business.objects.visible_in_search().values_list("pk", flat=True))
        self.assertIn(self.business.pk, visible)
        self.assertNotIn(self.hidden_business.pk, visible)

    def test_product_visible_in_search_excludes_stale_and_inherited(self):
        visible = set(Product.objects.visible_in_search().values_list("pk", flat=True))
        self.assertIn(self.product.pk, visible)
        self.assertNotIn(self.hidden_product.pk, visible)
        self.assertNotIn(self.inherited_product.pk, visible)

    def test_product_inherits_business_status(self):
        self.assertTrue(self.inherited_product.inherits_business_status)
        self.assertEqual(
            self.inherited_product.freshness.tier,
            FreshnessTier.HIDDEN,
        )

    def test_directory_hides_stale_products_but_detail_still_works(self):
        client = Client()
        index = client.get(reverse("directory:index"), HTTP_HOST="localhost")
        self.assertEqual(index.status_code, 200)
        self.assertContains(index, "Fresh Item")
        self.assertNotContains(index, "Old Item")
        self.assertNotContains(index, "Inherited Stale")

        detail = client.get(
            self.hidden_product.get_absolute_url(),
            HTTP_HOST="localhost",
        )
        self.assertEqual(detail.status_code, 200)

    def test_marketplace_hides_stale_products_but_detail_still_works(self):
        client = Client()
        index = client.get(reverse("marketplace:index"), HTTP_HOST="localhost")
        self.assertEqual(index.status_code, 200)
        self.assertContains(index, "Fresh Item")
        self.assertNotContains(index, "Old Item")

        detail = client.get(
            self.hidden_product.get_marketplace_url(),
            HTTP_HOST="localhost",
        )
        self.assertEqual(detail.status_code, 200)

    def test_business_list_hides_stale_company_but_detail_still_works(self):
        client = Client()
        index = client.get(reverse("businesses:index"), HTTP_HOST="localhost")
        self.assertEqual(index.status_code, 200)
        self.assertContains(index, "Fresh Co")
        self.assertNotContains(index, "Stale Co")

        detail = client.get(
            self.hidden_business.get_absolute_url(),
            HTTP_HOST="localhost",
        )
        self.assertEqual(detail.status_code, 200)

    def test_every_verification_level_is_searchable(self):
        for level in VerificationLevel:
            with self.subTest(level=level):
                Business.objects.filter(pk=self.business.pk).update(
                    verification_level=level
                )
                self.assertTrue(
                    Business.objects.visible_in_search()
                    .filter(pk=self.business.pk)
                    .exists()
                )

    def test_discontinued_is_a_lifecycle_status_not_a_level(self):
        self.assertNotIn("discontinued", VerificationLevel.values)
        self.assertIn("discontinued", LifecycleStatus.values)

    def test_directory_hides_discontinued_product_and_business(self):
        client = Client()
        Product.objects.filter(pk=self.product.pk).update(
            lifecycle_status=LifecycleStatus.DISCONTINUED
        )
        index = client.get(reverse("directory:index"), HTTP_HOST="localhost")
        self.assertNotContains(index, "Fresh Item")

        Product.objects.filter(pk=self.product.pk).update(
            lifecycle_status=LifecycleStatus.ACTIVE
        )
        Business.objects.filter(pk=self.business.pk).update(
            lifecycle_status=LifecycleStatus.DISCONTINUED
        )
        index = client.get(reverse("directory:index"), HTTP_HOST="localhost")
        self.assertNotContains(index, "Fresh Item")

    def test_inactive_business_and_its_products_are_not_served(self):
        Business.objects.filter(pk=self.business.pk).update(is_active=False)
        client = Client()

        self.assertFalse(Business.objects.visible_in_search().filter(pk=self.business.pk).exists())
        self.assertFalse(Product.objects.visible_in_search().filter(pk=self.product.pk).exists())
        self.assertFalse(Product.objects.served().filter(pk=self.product.pk).exists())

        for url in ("directory:index", "marketplace:index", "businesses:index"):
            with self.subTest(url=url):
                response = client.get(reverse(url), HTTP_HOST="localhost")
                self.assertNotContains(response, "Fresh Item")
                self.assertNotContains(response, "Fresh Co")

        for url in (
            self.business.get_absolute_url(),
            self.product.get_absolute_url(),
            self.product.get_marketplace_url(),
        ):
            with self.subTest(url=url):
                response = client.get(url, HTTP_HOST="localhost")
                self.assertEqual(response.status_code, 404)

    def test_discontinued_business_is_served_but_not_searchable(self):
        Business.objects.filter(pk=self.business.pk).update(
            lifecycle_status=LifecycleStatus.DISCONTINUED,
            verification_level=VerificationLevel.SIMUDZA_VERIFIED,
        )
        client = Client()
        self.assertFalse(Business.objects.visible_in_search().filter(pk=self.business.pk).exists())
        self.assertTrue(Business.objects.served().filter(pk=self.business.pk).exists())
        for url in (self.business.get_absolute_url(), self.product.get_absolute_url()):
            with self.subTest(url=url):
                response = client.get(url, HTTP_HOST="localhost")
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "discontinued or withdrawn")
