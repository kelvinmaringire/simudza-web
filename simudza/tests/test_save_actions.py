from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from categories.models import Category


class SaveActionsTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_superuser(
            "admin", "admin@example.com", "pass"
        )
        self.client.force_login(self.staff)
        self.host = {"HTTP_HOST": "localhost"}
        self.category = Category.objects.create(name="Food", slug="food")
        self.edit_url = reverse("category:edit", args=[self.category.pk])

    def _post(self, url, **extra):
        data = {"name": "Food & Drink", "description": "", "is_active": "on", **extra}
        return self.client.post(url, data, **self.host)

    def test_edit_page_shows_save_continue_and_delete(self):
        response = self.client.get(self.edit_url, **self.host)
        self.assertContains(response, 'name="_continue"')
        self.assertContains(response, "Save and continue editing")
        self.assertContains(response, reverse("category:delete", args=[self.category.pk]))

    def test_save_returns_to_listing(self):
        response = self._post(self.edit_url)
        self.assertRedirects(response, reverse("category:index"), fetch_redirect_response=False)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Food & Drink")

    def test_save_and_continue_stays_on_edit(self):
        response = self._post(self.edit_url, _continue="1")
        self.assertRedirects(response, self.edit_url, fetch_redirect_response=False)

    def test_save_and_create_new_opens_blank_add_form(self):
        response = self.client.get(self.edit_url, **self.host)
        self.assertContains(response, "Save and create new")

        response = self._post(self.edit_url, _addanother="1")
        self.assertRedirects(response, reverse("category:add"), fetch_redirect_response=False)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Food & Drink")

        response = self._post(reverse("category:add"), _addanother="1", name="Drinks")
        self.assertTrue(Category.objects.filter(name="Drinks").exists())
        self.assertRedirects(response, reverse("category:add"), fetch_redirect_response=False)

    def test_create_and_continue_opens_new_object(self):
        response = self._post(reverse("category:add"), _continue="1", name="Drinks")
        created = Category.objects.get(name="Drinks")
        self.assertRedirects(
            response,
            reverse("category:edit", args=[created.pk]),
            fetch_redirect_response=False,
        )

    def test_create_page_has_no_delete(self):
        response = self.client.get(reverse("category:add"), **self.host)
        self.assertContains(response, "Save and continue editing")
        self.assertNotContains(response, 'class="button no"')
