from django.test import TestCase

from businesses.models import Business
from businesses.quality import ISSUE_LABELS, evaluate_business


class ContactIssueTests(TestCase):
    def _business(self, **kwargs):
        return Business.objects.create(name="Maker", slug="maker", **kwargs)

    def test_all_contact_fields_empty_is_not_contactable(self):
        report = evaluate_business(self._business())
        self.assertIn("missing_contact", report.issues)

    def test_address_only_is_not_contactable(self):
        business = self._business(address="12 Samora Machel Ave", town_or_city="Harare")
        self.assertIn("missing_contact", evaluate_business(business).issues)

    def test_any_one_of_website_email_or_phone_is_enough(self):
        for field, value in (
            ("website", "maker.co.zw"),
            ("email", "sales at maker"),
            ("phone", "ask for Tendai"),
        ):
            with self.subTest(field=field):
                Business.objects.all().delete()
                business = self._business(**{field: value})
                self.assertNotIn("missing_contact", evaluate_business(business).issues)

    def test_contact_format_is_not_validated(self):
        self.assertNotIn("invalid_contact", ISSUE_LABELS)
