from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from businesses.models import Business
from categories.models import Category
from inventory.models import Inventory
from marketplace.models import VariantOffer
from marketplace.offers import set_variant_price
from marketplace.tests.helpers import add_sellable_variant
from products.models import Product, ProductVariant


class MarketplaceProductDetailVariantTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user("m", "m@x.com", "pass")
        self.business = Business.objects.create(
            name="Mazoe Co",
            slug="mazoe-mp",
            owner=owner,
            verified_at=timezone.now(),
        )
        self.product = Product.objects.create(
            business=self.business,
            category=Category.objects.create(name="Drinks", slug="drinks-mp"),
            name="Mazoe Orange Crush",
            slug="mazoe-orange-crush-mp",
            status=Product.ProductStatus.PUBLISHED,
            marketplace_enabled=True,
            verified_at=timezone.now(),
        )
        self.first = add_sellable_variant(
            self.product,
            price="2.50",
            quantity=8,
            name="Orange Crush",
            size_value=Decimal("2"),
            size_unit="L",
        )
        ProductVariant.objects.filter(pk=self.first.pk).update(sort_order=1)
        self.first.refresh_from_db()
        self.second = ProductVariant.objects.create(
            product=self.product,
            name="Raspberry",
            sort_order=2,
            size_value=Decimal("2"),
            size_unit="L",
        )
        set_variant_price(self.second, Decimal("2.75"))
        VariantOffer.objects.filter(variant=self.second).update(
            stock_mode=VariantOffer.StockMode.TRACKED,
            is_available=True,
        )
        Inventory.objects.filter(variant=self.second).update(
            quantity=5,
            reserved_quantity=0,
        )
        self.url = self.product.get_marketplace_url()

    def test_renders_directory_style_variant_picker(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "product-variant-option")
        self.assertContains(response, 'name="variant"')
        self.assertContains(response, "Orange Crush")
        self.assertContains(response, "Raspberry")
        self.assertContains(response, "selectVariant")
        self.assertEqual(response.context["selected_variant"], self.first)
        self.assertEqual(len(response.context["picker_options"]), 2)

    def test_query_param_selects_variant(self):
        response = self.client.get(self.url, {"variant": self.second.pk})
        self.assertEqual(response.context["selected_variant"], self.second)
        self.assertContains(response, f'id="mp-variant-option-{self.second.pk}"')
