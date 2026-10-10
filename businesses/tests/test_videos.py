from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from businesses.models import Business, BusinessVideo
from businesses.videos import (
    BusinessVideoKind,
    ProductVideoKind,
    validate_youtube_url,
    youtube_video_id,
)
from categories.models import Category
from products.models import Product, ProductVideo

VIDEO_ID = "dQw4w9WgXcQ"


class YoutubeVideoIdTests(TestCase):
    def test_accepts_common_youtube_url_shapes(self):
        urls = [
            f"https://www.youtube.com/watch?v={VIDEO_ID}",
            f"https://youtube.com/watch?v={VIDEO_ID}&t=42s",
            f"https://m.youtube.com/watch?v={VIDEO_ID}",
            f"https://youtu.be/{VIDEO_ID}",
            f"https://youtu.be/{VIDEO_ID}?si=abc",
            f"https://www.youtube.com/shorts/{VIDEO_ID}",
            f"https://www.youtube.com/embed/{VIDEO_ID}",
            f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}",
            f"https://www.youtube.com/live/{VIDEO_ID}",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(youtube_video_id(url), VIDEO_ID)

    def test_rejects_non_youtube_urls(self):
        urls = [
            "",
            "https://vimeo.com/123456",
            "https://www.youtube.com/channel/UC123",
            "https://www.youtube.com/watch?v=short",
            f"https://evil.example/watch?v={VIDEO_ID}",
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertIsNone(youtube_video_id(url))
                with self.assertRaises(ValidationError):
                    validate_youtube_url(url)


class VideoDetailPageTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name="Glytime", slug="glytime")
        self.category = Category.objects.create(name="Cereals", slug="cereals")
        self.product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Breakfast Cereal",
            slug="breakfast-cereal",
        )

    def test_business_page_embeds_videos(self):
        BusinessVideo.objects.create(
            business=self.business,
            url=f"https://youtu.be/{VIDEO_ID}",
            title="Inside our mill",
            kind=BusinessVideoKind.BUSINESS_TOUR,
        )
        response = self.client.get(self.business.get_absolute_url())
        self.assertContains(
            response,
            f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}",
        )
        self.assertContains(response, "Inside our mill")
        self.assertContains(response, "Factory or business tour")

    def test_product_page_embeds_videos(self):
        ProductVideo.objects.create(
            product=self.product,
            url=f"https://www.youtube.com/watch?v={VIDEO_ID}",
            kind=ProductVideoKind.SERVICE_DEMONSTRATION,
        )
        response = self.client.get(self.product.get_absolute_url())
        self.assertContains(
            response,
            f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}",
        )
        self.assertContains(response, "Service demonstration")

    def test_no_video_section_without_videos(self):
        for url in (
            self.business.get_absolute_url(),
            self.product.get_absolute_url(),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertNotContains(response, "youtube-nocookie.com")


class BusinessVideoAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser("admin", "admin@x.com", "pass")
        self.business = Business.objects.create(name="Admin Biz", slug="admin-biz")
        self.client.force_login(self.admin)

    def test_edit_view_saves_video_inline(self):
        url = reverse("business:edit", args=[self.business.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Videos")

        data = {
            "name": self.business.name,
            "business_type": self.business.business_type,
            "verification_level": self.business.verification_level,
            "is_active": "on",
            "videos-TOTAL_FORMS": "1",
            "videos-INITIAL_FORMS": "0",
            "videos-MIN_NUM_FORMS": "0",
            "videos-MAX_NUM_FORMS": "1000",
            "videos-0-url": f"https://youtu.be/{VIDEO_ID}",
            "videos-0-title": "Farm visit",
            "videos-0-kind": BusinessVideoKind.PROJECT_PORTFOLIO,
            "videos-0-ORDER": "1",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302, response.content[:2000])
        video = self.business.videos.get()
        self.assertEqual(video.title, "Farm visit")
        self.assertEqual(video.youtube_id, VIDEO_ID)
        self.assertEqual(video.kind, BusinessVideoKind.PROJECT_PORTFOLIO)


class VideoKindChoicesTests(TestCase):
    """Business and product videos offer separate, short lists of kinds."""

    def test_business_videos_offer_company_kinds_only(self):
        values = set(dict(BusinessVideo._meta.get_field("kind").choices))
        self.assertEqual(values, set(BusinessVideoKind.values))
        self.assertNotIn("service_demonstration", values)

    def test_product_videos_offer_product_and_service_kinds_only(self):
        values = set(dict(ProductVideo._meta.get_field("kind").choices))
        self.assertEqual(values, set(ProductVideoKind.values))
        self.assertNotIn("project_portfolio", values)

    def test_lists_stay_short_for_admins(self):
        self.assertLessEqual(len(BusinessVideoKind.choices), 8)
        self.assertLessEqual(len(ProductVideoKind.choices), 8)
