from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from businesses.models import Business


class StaffVerifyListingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        owner = User.objects.create_user("owner", "owner@example.com", "pass")
        self.staff = User.objects.create_user(
            "staff", "staff@example.com", "pass", is_staff=True
        )
        self.member = User.objects.create_user("member", "m@x.com", "pass")
        self.business = Business.objects.create(
            name="Stale Co",
            slug="stale-co",
            owner=owner,
            verified_at=timezone.now() - timedelta(days=400),
        )
        self.url = reverse("accounts:verify_listing")

    def test_non_staff_is_forbidden(self):
        self.client.force_login(self.member)
        response = self.client.post(
            self.url,
            {"kind": "business", "pk": self.business.pk},
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 403)

    def test_get_is_not_allowed(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url, HTTP_HOST="localhost").status_code, 405)

    def test_staff_post_refreshes_verified_at(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            self.url,
            {
                "kind": "business",
                "pk": self.business.pk,
                "level": "source_verified",
            },
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)
        self.business.refresh_from_db()
        self.assertGreaterEqual(
            self.business.verified_at, timezone.now() - timedelta(minutes=1)
        )
