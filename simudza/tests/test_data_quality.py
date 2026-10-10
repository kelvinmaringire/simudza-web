from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from businesses.models import Business
from categories.models import Category
from duplicates.models import DuplicateFlag
from products.models import Product
from products.quality import evaluate_product, refresh_product_quality
from products.services import upsert_default_variant
from products.test_helpers import add_sellable_variant
from reviews.models import ProductReview, ReportReason, ReportStatus


class ProductQualityTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name="Maker",
            slug="maker",
            email="maker@example.com",
            phone="+263771234567",
            website="https://example.com",
            verified_at=timezone.now(),
        )
        self.category = Category.objects.create(name="Food", slug="food")

    def _product(self, **kwargs):
        defaults = {
            "business": self.business,
            "category": self.category,
            "name": "Sample",
            "slug": "sample",
            "short_description": "Tasty",
            "description": "Longer text",
            "verified_at": timezone.now(),
        }
        defaults.update(kwargs)
        product = Product.objects.create(**defaults)
        add_sellable_variant(product, price="5.00")
        return product

    def test_complete_product_scores_nine_without_image(self):
        product = self._product()
        report = evaluate_product(product)
        self.assertEqual(report.score, 9)
        self.assertIn("missing_image", report.issues)

    def test_missing_image_lowers_score_and_adds_issue(self):
        product = self._product()
        Product.objects.filter(pk=product.pk).update(image=None)
        product.refresh_from_db()
        report = evaluate_product(product)
        self.assertIn("missing_image", report.issues)
        self.assertLess(report.score, 10)

    def test_verification_expired_issue(self):
        old = timezone.now() - timedelta(days=400)
        product = self._product(verified_at=old)
        Business.objects.filter(pk=self.business.pk).update(verified_at=old)
        report = evaluate_product(product)
        self.assertIn("verification_expired", report.issues)

    def test_free_text_contact_is_accepted(self):
        self.business.email = "sales at maker dot co dot zw"
        self.business.phone = "ask for Tendai"
        self.business.save()
        product = self._product()
        report = evaluate_product(product)
        self.assertNotIn("invalid_contact", report.issues)
        self.assertTrue(next(c for c in report.checks if c.code == "contact").passed)

    def test_duplicate_suspected(self):
        other = self._product(name="Other", slug="other")
        product = self._product(name="Sample 2", slug="sample-2")
        first, second = (product, other) if product.pk < other.pk else (other, product)
        DuplicateFlag.objects.create(
            kind=DuplicateFlag.Kind.PRODUCT,
            product_a=first,
            product_b=second,
            score=90,
        )
        report = evaluate_product(product)
        self.assertIn("duplicate_suspected", report.issues)

    def test_customer_reported(self):
        product = self._product()
        ProductReview.objects.create(
            product=product,
            reason=ReportReason.PRICE_INCORRECT,
            status=ReportStatus.OPEN,
        )
        report = evaluate_product(product)
        self.assertIn("customer_reported", report.issues)

    def test_refresh_stores_score(self):
        product = self._product()
        refresh_product_quality(product)
        product.refresh_from_db()
        self.assertEqual(product.quality_score, 9)


class ProductQualitySignalTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name="Co",
            slug="co",
            website="https://co.example",
            email="a@b.com",
            phone="1234567",
            verified_at=timezone.now(),
        )
        self.category = Category.objects.create(name="C", slug="c")
        self.product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="P",
            slug="p",
            short_description="s",
            verified_at=timezone.now(),
        )
        upsert_default_variant(self.product, price="1")

    def test_business_website_clear_lowers_product_score(self):
        refresh_product_quality(self.product)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quality_score, 9)

        with self.captureOnCommitCallbacks(execute=True):
            self.business.website = ""
            self.business.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quality_score, 8)

    def test_business_cosmetic_edit_refreshes_business_only(self):
        Product.objects.filter(pk=self.product.pk).update(quality_checked_at=None)
        Business.objects.filter(pk=self.business.pk).update(quality_checked_at=None)
        with self.captureOnCommitCallbacks(execute=True):
            self.business.description = "New description"
            self.business.save()
        self.product.refresh_from_db()
        self.business.refresh_from_db()
        self.assertIsNone(self.product.quality_checked_at)
        self.assertIsNotNone(self.business.quality_checked_at)

    def test_business_review_refreshes_business_only(self):
        from reviews.models import BusinessReview

        Product.objects.filter(pk=self.product.pk).update(quality_checked_at=None)
        with self.captureOnCommitCallbacks(execute=True):
            BusinessReview.objects.create(
                business=self.business,
                reason=ReportReason.PRICE_INCORRECT,
                status=ReportStatus.OPEN,
            )
        self.product.refresh_from_db()
        self.business.refresh_from_db()
        self.assertIsNone(self.product.quality_checked_at)
        self.assertIn("customer_reported", self.business.quality_issues)

    def test_category_deactivation_refreshes_products(self):
        refresh_product_quality(self.product)
        with self.captureOnCommitCallbacks(execute=True):
            self.category.is_active = False
            self.category.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.quality_score, 8)
        self.assertIn("missing_category", self.product.quality_issues)

    def test_category_cosmetic_edit_skips_product_refresh(self):
        Product.objects.filter(pk=self.product.pk).update(quality_checked_at=None)
        with self.captureOnCommitCallbacks(execute=True):
            self.category.name = "Renamed"
            self.category.save()
        self.product.refresh_from_db()
        self.assertIsNone(self.product.quality_checked_at)

    def test_refresh_query_count_is_per_batch_not_per_product(self):
        for i in range(10):
            p = Product.objects.create(
                business=self.business,
                category=self.category,
                name=f"P{i}",
                slug=f"p-{i}",
            )
            upsert_default_variant(p, price="1")
        qs = Product.objects.filter(category=self.category)
        # products, variants, images, duplicates, reports, bulk update,
        # empty next batch
        with self.assertNumQueries(7):
            refresh_product_quality(qs)
        self.assertFalse(qs.filter(quality_checked_at__isnull=True).exists())


class DataQualityAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_superuser("admin", "a@example.com", "pass")
        self.business = Business.objects.create(name="B", slug="b")
        self.category = Category.objects.create(name="Cat", slug="cat")
        self.product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="P",
            slug="p",
        )
        refresh_product_quality(self.product)
        Product.objects.filter(pk=self.product.pk).update(
            quality_issues=["missing_image"]
        )
        self.client = Client()
        self.host = {"HTTP_HOST": "localhost"}

    def test_product_index_shows_quality_column(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("product:index"), **self.host)
        self.assertContains(response, "Data quality")

    def test_issue_filter(self):
        self.client.force_login(self.staff)
        url = reverse("product:index") + "?issue=missing_image"
        response = self.client.get(url, **self.host)
        self.assertContains(response, self.product.name)

    def test_data_quality_queue_page(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("simudza_data_quality_index"), **self.host)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Missing image")

    def _dashboard(self):
        self.client.force_login(self.staff)
        return self.client.get(reverse("simudza_data_quality_index"), **self.host)

    def test_dashboard_hides_zero_count_issues(self):
        response = self._dashboard()
        product_labels = [i["label"] for i in response.context["product_issues"]]
        self.assertEqual(product_labels, ["Missing image"])
        self.assertNotContains(response, "Missing manufacturer")
        self.assertContains(
            response, f'href="{reverse("product:index")}?issue=missing_image"'
        )

    def test_dashboard_shows_empty_message_for_sections_without_issues(self):
        response = self._dashboard()
        self.assertEqual(response.context["category_issues"], [])
        self.assertContains(response, "No issues found")

    def test_dashboard_keeps_score_band_links(self):
        response = self._dashboard()
        bands = response.context["product_score_bands"]
        self.assertEqual([b["label"] for b in bands], ["0–3", "4–6", "7–8", "9–10"])
        self.assertContains(
            response,
            f'href="{reverse("product:index")}?quality_score_min=4&amp;quality_score_max=6"',
        )

    def test_dashboard_category_issue_links_to_filtered_index(self):
        tea = Category.objects.create(name="Tea", slug="tea", parent=self.category)
        response = self._dashboard()
        url = f'{reverse("category:index")}?issue=no_published_products'
        self.assertContains(response, f'href="{url}"')
        self.assertContains(response, "?needs_attention=yes")

        listing = self.client.get(url, **self.host)
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, reverse("category:edit", args=[tea.pk]))
