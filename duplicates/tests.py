from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from businesses.models import Business
from categories.models import Category
from products.forms import unique_product_slug
from products.models import Product
from products.test_helpers import add_sellable_variant

from .models import DuplicateFlag
from .normalize import (
    business_name_key,
    canonical_size,
    name_similarity,
    normalize_barcode,
    normalize_phones,
    product_name_key,
    website_key,
)
from .services import (
    flag_business_duplicates,
    flag_product_duplicates,
    review_flag,
    scan_for_duplicates,
)


class NormalizeTests(SimpleTestCase):
    def test_spelling_variants_of_a_name_are_identical(self):
        base, _ = product_name_key("Coca-Cola")
        for name in ("Coca Cola", "coca cola", "Cocacola", "COCA–COLA"):
            tokens, _ = product_name_key(name)
            self.assertEqual(name_similarity(base, tokens)[0], 1.0, name)

    def test_sizes_are_split_from_product_names(self):
        tokens, sizes = product_name_key("Coca Cola 500ml")
        self.assertEqual(tokens, ("coca", "cola"))
        self.assertEqual(sizes, {"500ml"})
        self.assertEqual(product_name_key("Mazoe 2 Litres")[1], {"2000ml"})
        self.assertEqual(product_name_key("Juice 6 x 330ml")[1], {"x6", "330ml"})

    def test_canonical_size_converts_units(self):
        self.assertEqual(canonical_size("1", "L"), canonical_size("1000", "ml"))
        self.assertEqual(canonical_size("2.5", "kg"), "2500g")
        self.assertEqual(canonical_size("1", "bags"), "")

    def test_business_names_ignore_legal_and_country_words(self):
        a, _ = business_name_key("Coca-Cola")
        b, _ = business_name_key("Coca Cola Zimbabwe (Pvt) Ltd")
        self.assertEqual(name_similarity(a, b)[0], 1.0)

    def test_different_flavours_are_not_similar(self):
        a, _ = product_name_key("Mazoe Raspberry")
        b, _ = product_name_key("Mazoe Blackberry")
        self.assertLess(name_similarity(a, b)[0], 0.75)

    def test_small_typos_still_match(self):
        a, _ = product_name_key("Mazoe Orange Crush")
        b, _ = product_name_key("Mazowe Orange Crush")
        self.assertGreaterEqual(name_similarity(a, b)[0], 0.9)

    def test_website_key_uses_registrable_domain(self):
        self.assertEqual(website_key("https://shop.schweppes.co.zw/"), "schweppes.co.zw")
        self.assertEqual(website_key("www.schweppes.co.zw"), "schweppes.co.zw")
        self.assertEqual(
            website_key("https://facebook.com/acme"), "facebook.com/acme"
        )
        self.assertEqual(website_key("https://facebook.com/"), "")

    def test_phone_and_barcode_normalisation(self):
        self.assertEqual(
            normalize_phones("0772 123 456 / +263 242 700 000"),
            {"263772123456", "263242700000"},
        )
        self.assertEqual(normalize_barcode("0 12345-67890 5"), "12345678905")


class DuplicateDetectionTestCase(TestCase):
    def setUp(self):
        self.delta = Business.objects.create(name="Delta Beverages", slug="delta")
        self.drinks = Category.objects.create(name="Drinks", slug="drinks")
        self.food = Category.objects.create(name="Food", slug="food")

    def product(self, name, *, business=None, category=None, brand="", **variant):
        product = Product.objects.create(
            business=business or self.delta,
            category=category or self.drinks,
            name=name,
            slug=unique_product_slug(name),
            brand_name=brand,
        )
        add_sellable_variant(product, **variant)
        return product


class ProductDuplicateTests(DuplicateDetectionTestCase):
    def test_spelling_variants_are_flagged(self):
        a = self.product("Coca-Cola", brand="Coca-Cola")
        b = self.product("Coca Cola", brand="Coca-Cola")

        flags = flag_product_duplicates(a)

        self.assertEqual(len(flags), 1)
        flag = flags[0]
        self.assertEqual({flag.product_a, flag.product_b}, {a, b})
        self.assertEqual(flag.status, DuplicateFlag.Status.OPEN)
        codes = {r["code"] for r in flag.reasons}
        self.assertIn("same_name", codes)
        self.assertIn("same_business", codes)

    def test_size_in_name_is_flagged_as_possible_variant(self):
        a = self.product("Coca-Cola", brand="Coca-Cola")
        b = self.product("Coca Cola 500ml", brand="Coca-Cola")

        flags = flag_product_duplicates(b)

        self.assertEqual(len(flags), 1)
        codes = {r["code"] for r in flags[0].reasons}
        self.assertIn("same_name_except_size", codes)
        self.assertEqual({flags[0].product_a, flags[0].product_b}, {a, b})

    def test_flavours_from_same_brand_are_not_flagged(self):
        a = self.product("Mazoe Raspberry", brand="Mazoe", size_value=2, size_unit="l")
        self.product("Mazoe Blackberry", brand="Mazoe", size_value=2, size_unit="l")
        self.product("Mazoe Orange Crush", brand="Mazoe", size_value=2, size_unit="l")

        self.assertEqual(flag_product_duplicates(a), [])

    def test_near_identical_variant_names_are_not_flagged(self):
        a = self.product("Minute Maid Refresh Orange", brand="Minute Maid")
        self.product("Minute Maid Refresh Lemon", brand="Minute Maid")

        self.assertEqual(flag_product_duplicates(a), [])

    def test_same_name_from_another_business_is_flagged_for_review(self):
        retailer = Business.objects.create(name="Corner Shop", slug="corner-shop")
        a = self.product("Coca Cola")
        self.product("Coca-Cola", business=retailer)

        self.assertEqual(len(flag_product_duplicates(a)), 1)

    def test_same_barcode_flags_regardless_of_name(self):
        importer = Business.objects.create(name="Importer", slug="importer")
        a = self.product("Classic Cola", barcode="06001234567890")
        b = self.product("Fizzy Drink", business=importer, category=self.food)
        b.variants.update(barcode="6001234567890")

        flags = flag_product_duplicates(a)

        self.assertEqual(len(flags), 1)
        self.assertIn("same_barcode", {r["code"] for r in flags[0].reasons})

    def test_not_a_duplicate_decision_survives_rescans(self):
        a = self.product("Coca-Cola")
        self.product("Coca Cola")
        flag = flag_product_duplicates(a)[0]

        review_flag(flag, status=DuplicateFlag.Status.DISTINCT, notes="Different sizes")
        scan_for_duplicates()

        flag.refresh_from_db()
        self.assertEqual(flag.status, DuplicateFlag.Status.DISTINCT)
        self.assertEqual(DuplicateFlag.objects.count(), 1)

    def test_new_identifier_reopens_a_dismissed_flag(self):
        a = self.product("Coca-Cola", barcode="111")
        b = self.product("Coca Cola")
        flag = flag_product_duplicates(a)[0]
        review_flag(flag, status=DuplicateFlag.Status.DISTINCT)

        b.variants.update(barcode="0111")
        flag_product_duplicates(b)

        flag.refresh_from_db()
        self.assertEqual(flag.status, DuplicateFlag.Status.OPEN)

    def test_open_flag_is_dropped_when_names_are_fixed(self):
        a = self.product("Coca-Cola")
        b = self.product("Coca Cola")
        flag_product_duplicates(a)

        b.name = "Sprite"
        b.save()
        flag_product_duplicates(b)

        self.assertFalse(DuplicateFlag.objects.exists())

    def test_archiving_a_product_clears_its_open_flags(self):
        a = self.product("Coca-Cola")
        b = self.product("Coca Cola")
        flag_product_duplicates(a)

        b.status = Product.ProductStatus.ARCHIVED
        b.save()
        flag_product_duplicates(a)

        self.assertFalse(DuplicateFlag.objects.exists())

    def test_detection_never_touches_listings(self):
        a = self.product("Coca-Cola")
        b = self.product("Coca Cola")
        flag = flag_product_duplicates(a)[0]
        review_flag(flag, status=DuplicateFlag.Status.DUPLICATE)

        self.assertEqual(Product.objects.filter(pk__in=[a.pk, b.pk]).count(), 2)
        b.refresh_from_db()
        self.assertEqual(b.status, Product.ProductStatus.PUBLISHED)

    def test_saving_a_product_runs_detection_after_commit(self):
        self.product("Coca-Cola")
        with self.captureOnCommitCallbacks(execute=True):
            self.product("Coca Cola")

        self.assertEqual(DuplicateFlag.objects.open().count(), 1)


class BusinessDuplicateTests(TestCase):
    def test_country_suffix_name_variant_is_flagged(self):
        a = Business.objects.create(name="Coca-Cola", slug="coca-cola")
        Business.objects.create(name="Coca Cola Zimbabwe (Pvt) Ltd", slug="cc-zim")

        flags = flag_business_duplicates(a)

        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0].kind, DuplicateFlag.Kind.BUSINESS)

    def test_same_website_domain_flags_different_names(self):
        a = Business.objects.create(
            name="Schweppes Zimbabwe",
            slug="schweppes",
            website="https://shop.schweppes.co.zw/",
        )
        Business.objects.create(
            name="Mazoe Drinks Division",
            slug="mazoe-div",
            website="http://www.schweppes.co.zw",
        )

        flags = flag_business_duplicates(a)

        self.assertEqual(len(flags), 1)
        self.assertIn("same_website", {r["code"] for r in flags[0].reasons})

    def test_shared_free_email_domain_is_not_evidence(self):
        a = Business.objects.create(name="Acme Foods", slug="acme", email="a@gmail.com")
        Business.objects.create(name="Bright Bakery", slug="bright", email="b@gmail.com")

        self.assertEqual(flag_business_duplicates(a), [])

    def test_distinct_businesses_are_not_flagged(self):
        a = Business.objects.create(name="National Foods", slug="national-foods")
        Business.objects.create(name="Glytime Foods", slug="glytime-foods")

        self.assertEqual(flag_business_duplicates(a), [])


class DuplicateAdminTests(DuplicateDetectionTestCase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.admin = User.objects.create_superuser("admin", "admin@x.com", "pass")
        self.client.force_login(self.admin)
        self.a = self.product("Coca-Cola")
        self.b = self.product("Coca Cola")
        self.flag = flag_product_duplicates(self.a)[0]

    def test_index_lists_flags(self):
        response = self.client.get(reverse("duplicate_flag:index"))
        self.assertContains(response, "Coca Cola")

    def test_review_records_decision_and_reviewer(self):
        url = reverse("duplicate_flag:edit", args=[self.flag.pk])
        self.assertContains(self.client.get(url), "Why this was flagged")

        response = self.client.post(
            url,
            {"status": DuplicateFlag.Status.DISTINCT, "review_notes": "Different recipes"},
        )

        self.assertEqual(response.status_code, 302)
        self.flag.refresh_from_db()
        self.assertEqual(self.flag.status, DuplicateFlag.Status.DISTINCT)
        self.assertEqual(self.flag.reviewed_by, self.admin)
        self.assertIsNotNone(self.flag.reviewed_at)
        self.assertTrue(Product.objects.filter(pk=self.b.pk).exists())

    def test_product_edit_page_shows_possible_duplicates(self):
        response = self.client.get(reverse("product:edit", args=[self.a.pk]))
        self.assertContains(response, "Possible duplicate of")
        self.assertContains(response, reverse("duplicate_flag:edit", args=[self.flag.pk]))
