import json
import uuid
from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from businesses.models import Business
from categories.models import Category
from marketplace.cart_analytics import cart_analytics_summary
from marketplace.cart_lifecycle import CartStatus, lifecycle_status_for_cart
from marketplace.cart_workflow import merge_guest_cart, sync_cart
from inventory.models import Inventory
from marketplace.models import (
    Cart,
    CartEvent,
    CartItem,
    Checkout,
    Order,
    VariantOffer,
)
from marketplace.offers import (
    product_has_sellable_variants,
    sellable_variants,
    set_variant_price,
    with_sellable_variants,
)
from marketplace.services import get_marketplace_products
from marketplace.test_helpers import add_sellable_variant
from products.models import Product, ProductVariant


class VariantOfferTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Offer", slug="offer")
        self.business = Business.objects.create(name="Offer Co", slug="offer-co")
        self.product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Juice",
            slug="juice",
        )

    def test_offer_created_when_variant_saved(self):
        variant = ProductVariant.objects.create(product=self.product, name="330 ml")
        offer = VariantOffer.objects.get(variant=variant)
        self.assertIsNone(offer.price)
        self.assertTrue(offer.is_available)

    def test_set_variant_price_updates_offer(self):
        variant = ProductVariant.objects.create(product=self.product, name="330 ml")
        set_variant_price(variant, Decimal("3.00"))
        self.assertEqual(VariantOffer.objects.get(variant=variant).price, Decimal("3.00"))

    def test_with_sellable_variants_annotates_from_price(self):
        add_sellable_variant(self.product, price="5.00", quantity=3)
        row = with_sellable_variants(Product.objects.all()).get(pk=self.product.pk)
        self.assertEqual(row.from_price, Decimal("5.00"))
        self.assertEqual(row.sellable_variant_count, 1)

    def test_sellable_excludes_zero_stock(self):
        variant = add_sellable_variant(self.product, price="5.00", quantity=0)
        self.assertFalse(sellable_variants().filter(pk=variant.pk).exists())

    def test_sellable_excludes_unpriced_and_unavailable(self):
        variant = add_sellable_variant(self.product, price=None, quantity=5)
        self.assertFalse(product_has_sellable_variants(self.product))

        set_variant_price(variant, Decimal("2.00"))
        self.assertTrue(product_has_sellable_variants(self.product))

        VariantOffer.objects.filter(variant=variant).update(is_available=False)
        self.assertFalse(product_has_sellable_variants(self.product))

    def test_deleting_variant_removes_it_from_carts_but_keeps_events(self):
        variant = add_sellable_variant(self.product, price="5.00", quantity=3)
        cart = Cart.objects.create()
        CartItem.objects.create(cart=cart, variant=variant, quantity=2)
        event = CartEvent.objects.create(
            cart=cart, variant=variant, kind=CartEvent.Kind.ADDED, quantity=2
        )

        variant.delete()

        self.assertFalse(CartItem.objects.filter(cart=cart).exists())
        event.refresh_from_db()
        self.assertIsNone(event.variant_id)

    def test_sellable_respects_reserved_stock(self):
        variant = add_sellable_variant(self.product, price="5.00", quantity=2)
        Inventory.objects.filter(variant=variant).update(reserved_quantity=2)
        self.assertFalse(sellable_variants().filter(pk=variant.pk).exists())


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
        self.token = str(uuid.uuid4())

    def test_get_marketplace_products_uses_variants(self):
        ids = list(get_marketplace_products().values_list("pk", flat=True))
        self.assertIn(self.product.pk, ids)

    def test_guest_cart_created_on_first_item_only(self):
        empty = sync_cart(token=self.token, user=None, items=[])
        self.assertIsNone(empty)
        self.assertFalse(Cart.objects.filter(token=self.token).exists())

        sync_cart(
            token=self.token,
            user=None,
            items=[{"variant_id": self.variant.pk, "quantity": 2}],
        )
        cart = Cart.objects.get(token=self.token)
        self.assertIsNone(cart.user_id)
        self.assertEqual(cart.items.filter(removed_at__isnull=True).count(), 1)

    def test_sync_emits_events_and_soft_removes(self):
        sync_cart(
            token=self.token,
            user=self.user,
            items=[{"variant_id": self.variant.pk, "quantity": 2}],
        )
        cart = Cart.objects.open().get(user=self.user)
        self.assertEqual(
            CartEvent.objects.filter(cart=cart, kind=CartEvent.Kind.ADDED).count(),
            1,
        )

        sync_cart(token=self.token, user=self.user, items=[], apply=True)
        item = cart.items.get(variant=self.variant)
        self.assertIsNotNone(item.removed_at)
        self.assertEqual(
            CartEvent.objects.filter(cart=cart, kind=CartEvent.Kind.REMOVED).count(),
            1,
        )

    def test_merge_guest_cart_keeps_higher_quantity(self):
        guest = Cart.objects.create(token=uuid.uuid4(), last_activity_at=timezone.now())
        CartItem.objects.create(
            cart=guest,
            variant=self.variant,
            quantity=3,
            price_snapshot=Decimal("4.50"),
        )
        user_cart = Cart.objects.create(
            user=self.user,
            token=uuid.uuid4(),
            last_activity_at=timezone.now(),
        )
        CartItem.objects.create(
            cart=user_cart,
            variant=self.variant,
            quantity=1,
            price_snapshot=Decimal("4.50"),
        )

        merge_guest_cart(guest, self.user)
        guest.refresh_from_db()
        self.assertIsNotNone(guest.merged_into_id)
        merged = Cart.objects.open().get(user=self.user)
        self.assertEqual(
            merged.items.get(variant=self.variant, removed_at__isnull=True).quantity,
            3,
        )

    def test_cart_sync_endpoint_guest_and_user(self):
        payload = {
            "token": self.token,
            "items": [{"variant_id": self.variant.pk, "quantity": 1}],
        }
        guest_response = self.client.post(
            reverse("marketplace:cart_sync"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(guest_response.status_code, 204)

        self.client.force_login(self.user)
        user_response = self.client.post(
            reverse("marketplace:cart_sync"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(user_response.status_code, 200)
        data = user_response.json()
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["id"], self.variant.pk)

    def test_checkout_marks_cart_converted(self):
        cart = Cart.objects.create(
            user=self.user,
            token=uuid.uuid4(),
            last_activity_at=timezone.now(),
        )
        CartItem.objects.create(
            cart=cart,
            variant=self.variant,
            quantity=2,
            price_snapshot=Decimal("4.50"),
        )
        checkout = Checkout.objects.create(user=self.user, cart=cart)
        order = checkout.complete()
        cart.refresh_from_db()
        self.assertIsNotNone(cart.converted_at)
        self.assertEqual(
            CartEvent.objects.filter(cart=cart, kind=CartEvent.Kind.CONVERTED).count(),
            1,
        )
        line = order.items.get()
        self.assertEqual(line.unit_price, Decimal("4.50"))
        self.assertEqual(order.subtotal, Decimal("9.00"))

    def test_lifecycle_status_thresholds(self):
        now = timezone.now()
        self.assertEqual(
            lifecycle_status_for_cart(
                last_activity_at=now - timedelta(hours=1),
                converted_at=None,
                merged_into_id=None,
                now=now,
            ),
            CartStatus.ACTIVE,
        )
        self.assertEqual(
            lifecycle_status_for_cart(
                last_activity_at=now - timedelta(days=2),
                converted_at=None,
                merged_into_id=None,
                now=now,
            ),
            CartStatus.INACTIVE,
        )
        self.assertEqual(
            lifecycle_status_for_cart(
                last_activity_at=now - timedelta(days=10),
                converted_at=None,
                merged_into_id=None,
                now=now,
            ),
            CartStatus.ABANDONED,
        )

    def test_cart_analytics_summary(self):
        cart = Cart.objects.create(
            user=self.user,
            token=uuid.uuid4(),
            last_activity_at=timezone.now() - timedelta(days=10),
        )
        CartItem.objects.create(
            cart=cart,
            variant=self.variant,
            quantity=2,
            price_snapshot=Decimal("4.50"),
        )
        summary = cart_analytics_summary()
        self.assertGreaterEqual(summary["status_rows"][2][1], 1)
        self.assertGreater(summary["abandoned_cart_value"], 0)
