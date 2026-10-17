from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from businesses.models import Business
from categories.models import Category
from inventory.models import Inventory
from inventory.viewsets import InventoryViewSet
from marketplace.models import VariantOffer
from products.models import Product, ProductVariant


class InventoryAdminTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Inv Admin", slug="inv-admin")
        self.business = Business.objects.create(
            name="Inv Admin Co", slug="inv-admin-co"
        )
        self.admin = get_user_model().objects.create_superuser(
            "inv-admin", "inv-admin@x.com", "pass"
        )

    def test_admin_queryset_only_tracked_marketplace_stock(self):
        tracked = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Tracked Cereal",
            slug="tracked-inv",
            marketplace_enabled=True,
        )
        unlimited = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Unlimited Honey",
            slug="unlimited-inv",
            marketplace_enabled=True,
        )
        directory_only = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Directory Tea",
            slug="directory-inv",
            marketplace_enabled=False,
        )
        tracked_inv = Inventory.objects.get(
            variant=ProductVariant.objects.create(product=tracked, name="A")
        )
        unlimited_inv = Inventory.objects.get(
            variant=ProductVariant.objects.create(product=unlimited, name="B")
        )
        directory_inv = Inventory.objects.get(
            variant=ProductVariant.objects.create(product=directory_only, name="C")
        )
        VariantOffer.objects.filter(variant=tracked_inv.variant).update(
            stock_mode=VariantOffer.StockMode.TRACKED
        )
        # unlimited keeps default UNLIMITED; directory stays out via marketplace_enabled

        viewset = InventoryViewSet()
        qs = viewset.get_queryset()
        self.assertIn(tracked_inv, qs)
        self.assertNotIn(unlimited_inv, qs)
        self.assertNotIn(directory_inv, qs)
        self.assertEqual(
            set(viewset.get_common_view_kwargs()["queryset"].values_list("pk", flat=True)),
            set(qs.values_list("pk", flat=True)),
        )

        client = Client()
        client.force_login(self.admin)
        response = client.get(reverse("inventory:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tracked Cereal")
        self.assertNotContains(response, "Unlimited Honey")
        self.assertNotContains(response, "Directory Tea")
