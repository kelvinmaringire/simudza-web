from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from businesses.models import Business
from categories.models import Category
from marketplace.tests.helpers import add_sellable_variant
from marketplace.viewsets import VariantOfferViewSet
from products.models import Product


class VariantOfferAdminTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Offer Admin", slug="offer-admin")
        self.business = Business.objects.create(
            name="Offer Admin Co", slug="offer-admin-co"
        )
        self.admin = get_user_model().objects.create_superuser(
            "offer-admin", "offer-admin@x.com", "pass"
        )

    def test_admin_queryset_only_marketplace_enabled(self):
        listed = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Listed Juice",
            slug="listed",
            marketplace_enabled=True,
        )
        directory_only = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Directory Honey",
            slug="directory",
            marketplace_enabled=False,
        )
        listed_offer = add_sellable_variant(listed).offer
        directory_offer = add_sellable_variant(
            directory_only, enable_marketplace=False
        ).offer

        viewset = VariantOfferViewSet()
        qs = viewset.get_queryset()
        self.assertIn(listed_offer, qs)
        self.assertNotIn(directory_offer, qs)
        self.assertIs(viewset.get_common_view_kwargs()["queryset"].model, qs.model)
        self.assertEqual(
            set(viewset.get_common_view_kwargs()["queryset"].values_list("pk", flat=True)),
            set(qs.values_list("pk", flat=True)),
        )

        client = Client()
        client.force_login(self.admin)
        response = client.get(reverse("variant_offer:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Listed Juice")
        self.assertNotContains(response, "Directory Honey")
