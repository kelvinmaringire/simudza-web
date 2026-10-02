import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from businesses.models import Business
from categories.models import Category
from marketplace.models import Cart, CartItem, Checkout, Order
from marketplace.services import get_marketplace_products, sync_user_cart
from products.models import Product
from products.test_helpers import add_sellable_variant


class MarketplaceVariantCartTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("buyer", "b@x.com", "pass")
        self.category = Category.objects.create(name="Shop", slug="shop")
        self.business = Business.objects.create(name="Maker", slug="maker")
        self.product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Tea",
            slug="tea",
            status=Product.ProductStatus.PUBLISHED,
        )
        self.variant = add_sellable_variant(self.product, price="4.50", quantity=5)
        self.client = Client()

    def test_get_marketplace_products_uses_variants(self):
        ids = list(get_marketplace_products().values_list("pk", flat=True))
        self.assertIn(self.product.pk, ids)

    def test_sync_user_cart_accepts_variant_id(self):
        sync_user_cart(
            self.user,
            [{"variant_id": self.variant.pk, "quantity": 2}],
        )
        cart = Cart.objects.get(user=self.user)
        item = cart.items.get()
        self.assertEqual(item.variant_id, self.variant.pk)
        self.assertEqual(item.quantity, 2)

    def test_cart_sync_endpoint(self):
        self.client.force_login(self.user)
        payload = {"items": [{"variant_id": self.variant.pk, "quantity": 1}]}
        response = self.client.post(
            reverse("marketplace:cart_sync"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 1)

    def test_checkout_prices_from_variant(self):
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=2)
        checkout = Checkout.objects.create(user=self.user, cart=cart)
        order = checkout.complete()
        line = order.items.get()
        self.assertEqual(line.unit_price, Decimal("4.50"))
        self.assertEqual(line.variant_id, self.variant.pk)
        self.assertEqual(line.variant_label, self.variant.label)
        self.assertEqual(order.subtotal, Decimal("9.00"))
