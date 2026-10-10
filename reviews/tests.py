from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from businesses.models import Business
from businesses.verification.levels import VerificationLevel
from categories.models import Category
from products.models import Product
from reviews.models import (
    BusinessReview,
    ProductReview,
    ReportReason,
    ReportStatus,
)
from reviews.views import REPORT_LIMIT


class ListingReportTests(TestCase):
    def setUp(self):
        cache.clear()
        owner = get_user_model().objects.create_user("owner", "o@x.com", "pass")
        self.member = get_user_model().objects.create_user("member", "m@x.com", "pass")
        self.staff = get_user_model().objects.create_user(
            "staff", "s@x.com", "pass", is_staff=True, is_superuser=True
        )
        self.category = Category.objects.create(name="Cat", slug="cat")
        self.business = Business.objects.create(
            name="Biz",
            slug="biz",
            owner=owner,
        )
        self.product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Prod",
            slug="prod",
        )
        self.client = Client()

    def test_guest_product_report_creates_open_unpublished_review(self):
        url = reverse("reviews:report_product", kwargs={"slug": self.product.slug})
        response = self.client.post(
            url,
            {
                "reason": ReportReason.PRODUCT_DISCONTINUED,
                "details": "Not on shelves anymore",
            },
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)
        review = ProductReview.objects.get()
        self.assertEqual(review.reason, ReportReason.PRODUCT_DISCONTINUED)
        self.assertEqual(review.status, ReportStatus.OPEN)
        self.assertIsNone(review.user_id)
        self.assertFalse(review.is_published)
        self.assertIsNone(review.rating)

    def test_member_business_report_allows_multiple_reports(self):
        url = reverse("reviews:report_business", kwargs={"slug": self.business.slug})
        self.client.force_login(self.member)
        for _ in range(2):
            response = self.client.post(
                url,
                {"reason": ReportReason.BUSINESS_CLOSED},
                HTTP_HOST="localhost",
            )
            self.assertEqual(response.status_code, 302)
        self.assertEqual(BusinessReview.objects.filter(user=self.member).count(), 2)

    def test_invalid_reason_for_business_rejected(self):
        url = reverse("reviews:report_business", kwargs={"slug": self.business.slug})
        response = self.client.post(
            url,
            {"reason": ReportReason.PRICE_INCORRECT},
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BusinessReview.objects.count(), 0)

    def test_honeypot_drops_submission(self):
        url = reverse("reviews:report_product", kwargs={"slug": self.product.slug})
        response = self.client.post(
            url,
            {
                "reason": ReportReason.PRODUCT_DISCONTINUED,
                "website": "http://spam.example",
            },
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ProductReview.objects.count(), 0)

    def test_throttle_blocks_after_limit(self):
        url = reverse("reviews:report_product", kwargs={"slug": self.product.slug})
        for i in range(REPORT_LIMIT):
            response = self.client.post(
                url,
                {"reason": ReportReason.PRODUCT_DISCONTINUED, "details": f"try {i}"},
                HTTP_HOST="localhost",
            )
            self.assertEqual(response.status_code, 302)
        self.assertEqual(ProductReview.objects.count(), REPORT_LIMIT)

        response = self.client.post(
            url,
            {"reason": ReportReason.PRODUCT_DISCONTINUED, "details": "blocked"},
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ProductReview.objects.count(), REPORT_LIMIT)

    def test_mark_verified_resolves_open_product_reports(self):
        ProductReview.objects.create(
            product=self.product,
            reason=ReportReason.PRICE_INCORRECT,
            status=ReportStatus.OPEN,
            is_published=False,
        )
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("accounts:verify_listing"),
            {
                "kind": "product",
                "pk": self.product.pk,
                "level": VerificationLevel.SIMUDZA_VERIFIED,
            },
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)
        review = ProductReview.objects.get()
        self.assertEqual(review.status, ReportStatus.RESOLVED)
        self.assertIsNotNone(review.resolved_at)

    def test_staff_dashboard_shows_open_report_context(self):
        ProductReview.objects.create(
            product=self.product,
            reason=ReportReason.DUPLICATE_LISTING,
            status=ReportStatus.OPEN,
            is_published=False,
        )
        self.client.force_login(self.staff)
        response = self.client.get(reverse("accounts:dashboard"), HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open customer reports")
        self.assertContains(response, "Duplicate listing")

    def test_wagtail_admin_review_lists_load_for_superuser(self):
        self.client.force_login(self.staff)
        product_admin = self.client.get("/admin/product_review/", HTTP_HOST="localhost")
        business_admin = self.client.get("/admin/business_review/", HTTP_HOST="localhost")
        self.assertEqual(product_admin.status_code, 200)
        self.assertEqual(business_admin.status_code, 200)
