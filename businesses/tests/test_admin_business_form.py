from django.contrib.auth import get_user_model
from django.test import TestCase

from businesses.models import Business


class BusinessAdminOwnerDefaultTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser("admin", "a@x.com", "pass")
        self.saved_owner = User.objects.create_user("saved", "s@x.com", "pass")
        self.client.force_login(self.admin)

    def _owner_initial(self, url):
        response = self.client.get(url, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        return response.context["form"]["owner"].value()

    def test_new_business_defaults_owner_to_logged_in_user(self):
        self.assertEqual(self._owner_initial("/admin/business/new/"), self.admin.pk)

    def test_non_superuser_staff_cannot_raise_level_to_simudza_verified(self):
        from businesses.forms import BusinessForm
        from businesses.verification.levels import VerificationLevel

        staff = get_user_model().objects.create_user("staff", "st@x.com", "pass", is_staff=True)
        business = Business.objects.create(name="Plain", slug="plain")
        form = BusinessForm(
            data={
                "name": "Plain",
                "business_type": "other",
                "verification_level": VerificationLevel.SIMUDZA_VERIFIED,
                "lifecycle_status": "active",
            },
            instance=business,
            for_user=staff,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("verification_level", form.errors)

        business.verification_level = VerificationLevel.SIMUDZA_VERIFIED
        business.save()
        form = BusinessForm(
            data={
                "name": "Plain renamed",
                "business_type": "other",
                "verification_level": VerificationLevel.SIMUDZA_VERIFIED,
                "lifecycle_status": "active",
            },
            instance=business,
            for_user=staff,
        )
        form.is_valid()
        self.assertNotIn("verification_level", form.errors)

    def test_edit_keeps_saved_owner(self):
        business = Business.objects.create(name="Owned", slug="owned", owner=self.saved_owner)
        self.assertEqual(
            self._owner_initial(f"/admin/business/edit/{business.pk}/"),
            self.saved_owner.pk,
        )
