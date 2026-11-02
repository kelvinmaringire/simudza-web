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
from marketplace.cart.cart_analytics import cart_analytics_summary
from marketplace.cart.cart_lifecycle import CartStatus, lifecycle_status_for_cart
from marketplace.cart.cart_workflow import merge_guest_cart, serialize_cart_lines, sync_cart
from marketplace.models import (
    Cart,
    CartEvent,
    CartItem,
    Checkout,
    PaymentStatus,
    VariantOffer,
)
from marketplace.services import get_marketplace_products
from marketplace.tests.helpers import add_sellable_variant
from products.models import Product


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

    def test_sync_after_converted_cart_reuses_client_token_safely(self):
        """Converted carts keep their token; a new open cart must not collide."""
        token = uuid.uuid4()
        old = Cart.objects.create(
            user=self.user,
            token=token,
            last_activity_at=timezone.now(),
            converted_at=timezone.now(),
        )
        cart = sync_cart(
            token=str(token),
            user=self.user,
            items=[{"variant_id": self.variant.pk, "quantity": 1}],
        )
        self.assertIsNotNone(cart)
        self.assertNotEqual(cart.pk, old.pk)
        self.assertNotEqual(cart.token, token)
        self.assertIsNone(cart.converted_at)
        self.assertEqual(cart.items.filter(removed_at__isnull=True).count(), 1)

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
        checkout = Checkout.objects.create(
            user=self.user,
            cart=cart,
            customer_name="Test User",
            customer_email=self.user.email or "test@example.com",
            payment_status=PaymentStatus.PAID,
            paid_at=timezone.now(),
        )
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

    def test_unlimited_variant_with_zero_stock_stays_in_cart(self):
        """Unlimited offers must not be clamped to inventory.available_quantity (0)."""
        product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Juice",
            slug="juice-unlimited",
            status=Product.ProductStatus.PUBLISHED,
            marketplace_enabled=True,
        )
        variant = add_sellable_variant(
            product,
            price="100.00",
            quantity=0,
            stock_mode=VariantOffer.StockMode.UNLIMITED,
            name="Orange",
        )
        cart = sync_cart(
            token=str(uuid.uuid4()),
            user=None,
            items=[{"variant_id": variant.pk, "quantity": 2}],
        )
        self.assertIsNotNone(cart)
        line = cart.items.get(variant=variant, removed_at__isnull=True)
        self.assertEqual(line.quantity, 2)
        payload = serialize_cart_lines(cart)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["quantity"], 2)
        self.assertEqual(payload[0]["maxQty"], 99)

    def test_serialize_cart_lines_prefers_variant_image(self):
        from io import BytesIO

        from django.core.files.images import ImageFile
        from PIL import Image as PILImage
        from wagtail.images.models import Image

        from products.models import ProductVariantImage

        def make_image(name, color):
            buf = BytesIO()
            PILImage.new("RGB", (32, 32), color).save(buf, format="PNG")
            buf.seek(0)
            return Image.objects.create(
                title=name,
                file=ImageFile(buf, name=f"{name}.png"),
            )

        product_img = make_image("product", (200, 0, 0))
        variant_img = make_image("variant", (0, 200, 0))
        self.product.image = product_img
        self.product.save(update_fields=["image"])
        ProductVariantImage.objects.create(variant=self.variant, image=variant_img)

        cart = Cart.objects.create(
            token=uuid.uuid4(),
            last_activity_at=timezone.now(),
        )
        CartItem.objects.create(
            cart=cart,
            variant=self.variant,
            quantity=1,
            price_snapshot=Decimal("4.50"),
        )
        payload = serialize_cart_lines(cart)
        self.assertEqual(len(payload), 1)
        self.assertEqual(
            payload[0]["imageUrl"],
            variant_img.get_rendition("fill-96x96").url,
        )
        self.assertNotEqual(
            payload[0]["imageUrl"],
            product_img.get_rendition("fill-96x96").url,
        )
