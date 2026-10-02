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
        )
        self.category = Category.objects.create(
            name="Food",
            slug="food",
            description="Food products",
        )

    def _product(self, **kwargs):
        defaults = {
            "business": self.business,
            "category": self.category,
            "name": "Sample",
            "slug": "sample",
            "short_description": "Tasty",
            "description": "Longer text",
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

    def test_invalid_contact_on_business(self):
        self.business.email = "not-an-email"
        self.business.save()
        product = self._product()
        report = evaluate_product(product)
        self.assertIn("invalid_contact", report.issues)

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
        )
        self.category = Category.objects.create(name="C", slug="c", description="x")
        self.product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="P",
            slug="p",
            short_description="s",
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
