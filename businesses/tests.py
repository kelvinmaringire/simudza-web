from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from businesses.models import Business
from businesses.verification import FreshnessTier, freshness_for
from categories.models import Category
from directory.models import DirectoryListing
from products.models import Product


class VerificationFreshnessTests(TestCase):
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


class VerificationVisibilityTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(
            "owner",
            "owner@example.com",
            "pass",
        )
        self.staff = get_user_model().objects.create_user(
            "staff",
            "staff@example.com",
            "pass",
            is_staff=True,
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
        from products.test_helpers import add_sellable_variant

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

    def test_verify_listing_requires_staff_and_post(self):
        client = Client()
        url = reverse("accounts:verify_listing")
        self.hidden_business.verified_at = timezone.now() - timedelta(days=400)
        self.hidden_business.save(update_fields=["verified_at"])

        client.force_login(get_user_model().objects.create_user("member", "m@x.com", "pass"))
        denied = client.post(
            url,
            {"kind": "business", "pk": self.hidden_business.pk},
            HTTP_HOST="localhost",
        )
        self.assertEqual(denied.status_code, 403)

        client.force_login(self.staff)
        self.assertEqual(client.get(url, HTTP_HOST="localhost").status_code, 405)

        ok = client.post(
            url,
            {
                "kind": "business",
                "pk": self.hidden_business.pk,
                "level": "simudza_checked",
            },
            HTTP_HOST="localhost",
        )
        self.assertEqual(ok.status_code, 302)
        self.hidden_business.refresh_from_db()
        self.assertGreaterEqual(self.hidden_business.verified_at, timezone.now() - timedelta(minutes=1))


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
