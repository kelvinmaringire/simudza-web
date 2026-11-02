import uuid
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from businesses.models import Business
from categories.models import Category
from inventory.models import Inventory
from inventory.services import commit_stock, release_stock, reserve_stock
from marketplace.checkout.checkout_workflow import (
    apply_paystack_success,
    finish_paid_checkout,
    get_or_start_checkout,
    place_order,
    update_customer,
    update_fulfilment,
)
from marketplace.models import (
    Cart,
    CartItem,
    Checkout,
    FulfilmentMethod,
    Order,
    PaymentProvider,
    PaymentStatus,
    VariantOffer,
)
from marketplace.payments import paystack
from marketplace.tests.helpers import add_sellable_variant
from products.models import Product

User = get_user_model()


@override_settings(
    PAYSTACK_PUBLIC_KEY="pk_test_x",
    PAYSTACK_SECRET_KEY="sk_test_x",
    PAYSTACK_CURRENCY="ZAR",
    MARKETPLACE_DELIVERY_FEE="5.00",
)
class CheckoutWorkflowTests(TestCase):
    def setUp(self):
        from marketplace.settings import MarketplaceCurrency, MarketplaceSettings

        MarketplaceSettings.objects.update_or_create(
            defaults={"currency": MarketplaceCurrency.ZAR},
        )
        self.user = User.objects.create_user(
            username="buyer",
            email="buyer@example.com",
            password="pass12345",
        )
        self.user.first_name = "Buyer"
        self.user.save()
        self.category = Category.objects.create(name="Shop", slug="shop-checkout")
        self.business = Business.objects.create(name="Checkout Maker", slug="checkout-maker")
        self.product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Checkout Product",
            slug="checkout-product",
            status=Product.ProductStatus.PUBLISHED,
            marketplace_enabled=True,
        )
        self.variant = add_sellable_variant(
            self.product,
            price="10.00",
            quantity=5,
            stock_mode=VariantOffer.StockMode.TRACKED,
        )
        self.cart = Cart.objects.create(
            user=self.user,
            token=uuid.uuid4(),
            last_activity_at=timezone.now(),
        )
        CartItem.objects.create(
            cart=self.cart,
            variant=self.variant,
            quantity=2,
            price_snapshot=Decimal("10.00"),
        )

    def test_get_or_start_checkout_creates_pending_checkout(self):
        checkout = get_or_start_checkout(self.user)
        self.assertEqual(checkout.user, self.user)
        self.assertEqual(checkout.cart, self.cart)
        self.assertEqual(checkout.status, Checkout.CheckoutStatus.PENDING)

    def test_reserve_and_commit_stock(self):
        reserve_stock(self.variant, 2)
        inventory = Inventory.objects.get(variant=self.variant)
        self.assertEqual(inventory.reserved_quantity, 2)
        self.assertEqual(inventory.available_quantity, 3)
        commit_stock(self.variant, 2)
        inventory.refresh_from_db()
        self.assertEqual(inventory.quantity, 3)
        self.assertEqual(inventory.reserved_quantity, 0)

    def test_release_stock(self):
        reserve_stock(self.variant, 2)
        release_stock(self.variant, 2)
        inventory = Inventory.objects.get(variant=self.variant)
        self.assertEqual(inventory.reserved_quantity, 0)

    @patch.object(paystack, "initialize_transaction")
    def test_place_order_initializes_paystack(self, mock_init):
        mock_init.return_value = {
            "authorization_url": "https://checkout.paystack.com/test",
            "access_code": "abc",
        }
        checkout = get_or_start_checkout(self.user)
        update_customer(
            checkout,
            name="Buyer Test",
            email="buyer@example.com",
            phone="+263771234567",
        )
        update_fulfilment(checkout, method=FulfilmentMethod.COLLECTION)
        checkout.payment_provider = PaymentProvider.PAYSTACK
        checkout.terms_accepted_at = timezone.now()
        checkout.save()
        result = place_order(
            checkout,
            callback_url="http://testserver/marketplace/checkout/payment/callback/",
        )
        self.assertEqual(result["authorization_url"], "https://checkout.paystack.com/test")
        checkout.refresh_from_db()
        self.assertEqual(checkout.payment_status, PaymentStatus.PENDING)
        self.assertTrue(checkout.payment_reference.startswith("sim-"))

    @patch.object(paystack, "verify_transaction")
    def test_apply_paystack_success_idempotent(self, mock_verify):
        mock_verify.return_value = {
            "status": "success",
            "amount": 2000,
            "currency": "ZAR",
            "customer": {"email": "buyer@example.com"},
        }
        checkout = get_or_start_checkout(self.user)
        update_customer(
            checkout,
            name="Buyer Test",
            email="buyer@example.com",
            phone="+263771234567",
        )
        update_fulfilment(checkout, method=FulfilmentMethod.COLLECTION)
        checkout.payment_provider = PaymentProvider.PAYSTACK
        checkout.payment_reference = "sim-test-ref"
        checkout.payment_status = PaymentStatus.PENDING
        checkout.terms_accepted_at = timezone.now()
        checkout.save()
        reserve_stock(self.variant, 2)
        checkout.stock_reservations.create(variant=self.variant, quantity=2)

        order = apply_paystack_success("sim-test-ref")
        self.assertEqual(order.status, Order.OrderStatus.CONFIRMED)
        self.assertEqual(order.payment_status, PaymentStatus.PAID)
        order2 = apply_paystack_success("sim-test-ref")
        self.assertEqual(order.pk, order2.pk)
        inventory = Inventory.objects.get(variant=self.variant)
        self.assertEqual(inventory.quantity, 3)

    def test_finish_paid_checkout_requires_paid_status(self):
        checkout = get_or_start_checkout(self.user)
        checkout.payment_status = PaymentStatus.UNPAID
        checkout.save()
        with self.assertRaises(Exception):
            finish_paid_checkout(checkout)

    def test_update_fulfilment_rejects_collection_when_disabled(self):
        from marketplace.checkout.checkout_workflow import CheckoutValidationError
        from marketplace.settings import MarketplaceSettings

        MarketplaceSettings.objects.update_or_create(
            defaults={"collection_enabled": False},
        )
        checkout = get_or_start_checkout(self.user)
        with self.assertRaises(CheckoutValidationError):
            update_fulfilment(checkout, method=FulfilmentMethod.COLLECTION)
        update_fulfilment(
            checkout,
            method=FulfilmentMethod.DELIVERY,
            city="Harare",
            suburb="Avondale",
            street="1 Main St",
        )
        checkout.refresh_from_db()
        self.assertEqual(checkout.fulfilment_method, FulfilmentMethod.DELIVERY)


class CheckoutViewTests(TestCase):
    def setUp(self):
        from marketplace.settings import MarketplaceCurrency, MarketplaceSettings

        MarketplaceSettings.objects.update_or_create(
            defaults={
                "currency": MarketplaceCurrency.ZAR,
                "collection_enabled": True,
            },
        )
        self.client = Client()
        self.user = User.objects.create_user(
            username="shopper",
            email="shopper@example.com",
            password="pass12345",
        )
        self.category = Category.objects.create(name="Shop", slug="shop-view")
        self.business = Business.objects.create(name="View Maker", slug="view-maker")
        self.product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="View Product",
            slug="view-product",
            status=Product.ProductStatus.PUBLISHED,
            marketplace_enabled=True,
        )
        self.variant = add_sellable_variant(self.product, price="8.00", quantity=10)
        self.cart = Cart.objects.create(
            user=self.user,
            token=uuid.uuid4(),
            last_activity_at=timezone.now(),
        )
        CartItem.objects.create(
            cart=self.cart,
            variant=self.variant,
            quantity=1,
            price_snapshot=Decimal("8.00"),
        )

    def test_checkout_requires_login(self):
        response = self.client.get(reverse("marketplace:checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/sign-in/", response.url)

    def test_checkout_cart_step_renders_for_logged_in_user(self):
        self.client.login(username="shopper", password="pass12345")
        response = self.client.get(reverse("marketplace:checkout_step", args=["cart"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review your cart")

    def test_delivery_step_hides_collection_when_disabled(self):
        from marketplace.settings import MarketplaceSettings

        MarketplaceSettings.objects.update_or_create(
            defaults={"collection_enabled": False},
        )
        self.client.login(username="shopper", password="pass12345")
        # Advance past cart + customer so delivery form is reachable.
        self.client.get(reverse("marketplace:checkout_step", args=["cart"]))
        self.client.post(reverse("marketplace:checkout_step", args=["cart"]))
        self.client.post(
            reverse("marketplace:checkout_step", args=["customer"]),
            {
                "customer_name": "Shopper",
                "customer_email": "shopper@example.com",
                "customer_phone": "+263771234567",
            },
        )
        response = self.client.get(
            reverse("marketplace:checkout_step", args=["delivery"])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Collection")
        self.assertContains(response, "name=\"fulfilment_method\"", html=False)
        self.assertContains(response, 'value="delivery"', html=False)

    def test_order_confirmation_requires_paid_order(self):
        self.client.login(username="shopper", password="pass12345")
        order = Order.objects.create(
            user=self.user,
            subtotal=Decimal("8.00"),
            total=Decimal("8.00"),
            payment_status=PaymentStatus.UNPAID,
        )
        response = self.client.get(
            reverse("marketplace:order_confirmation", args=[order.pk])
        )
        self.assertEqual(response.status_code, 302)
