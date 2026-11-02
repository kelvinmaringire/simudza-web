from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from businesses.models import Business
from categories.models import Category
from marketplace.checkout.checkout_workflow import (
    apply_paystack_success,
    checkout_totals,
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
from marketplace.settings import (
    MarketplaceCurrency,
    MarketplaceSettings,
    TaxPricingMode,
)
from marketplace.tax import calculate_tax, format_tax_rate
from marketplace.tests.helpers import add_sellable_variant
from products.models import Product

User = get_user_model()


class TaxCalculationTests(TestCase):
    def test_format_tax_rate_strips_trailing_zeros(self):
        self.assertEqual(format_tax_rate("15.5000"), "15.5")
        self.assertEqual(format_tax_rate("15.0000"), "15")
        self.assertEqual(format_tax_rate(Decimal("12.50")), "12.5")

    def test_tax_disabled(self):
        tax = calculate_tax(
            merchandise_subtotal="100.00",
            delivery_fee="5.00",
            enabled=False,
            rate_percent_value="15",
        )
        self.assertFalse(tax.enabled)
        self.assertEqual(tax.tax_amount, Decimal("0.00"))
        self.assertEqual(tax.total, Decimal("105.00"))

    def test_tax_excluded_15_percent(self):
        tax = calculate_tax(
            merchandise_subtotal="100.00",
            delivery_fee="0",
            enabled=True,
            pricing_mode=TaxPricingMode.EXCLUDED,
            rate_percent_value="15",
        )
        self.assertEqual(tax.tax_amount, Decimal("15.00"))
        self.assertEqual(tax.total, Decimal("115.00"))

    def test_tax_included_15_percent(self):
        tax = calculate_tax(
            merchandise_subtotal="115.00",
            delivery_fee="0",
            enabled=True,
            pricing_mode=TaxPricingMode.INCLUDED,
            rate_percent_value="15",
        )
        self.assertEqual(tax.tax_amount, Decimal("15.00"))
        self.assertEqual(tax.total, Decimal("115.00"))

    def test_zero_tax_rate(self):
        tax = calculate_tax(
            merchandise_subtotal="100.00",
            enabled=True,
            pricing_mode=TaxPricingMode.EXCLUDED,
            rate_percent_value="0",
        )
        self.assertEqual(tax.tax_amount, Decimal("0.00"))
        self.assertEqual(tax.total, Decimal("100.00"))

    def test_decimal_tax_rate_rounding(self):
        tax = calculate_tax(
            merchandise_subtotal="10.00",
            enabled=True,
            pricing_mode=TaxPricingMode.EXCLUDED,
            rate_percent_value="12.5",
        )
        self.assertEqual(tax.tax_amount, Decimal("1.25"))
        self.assertEqual(tax.total, Decimal("11.25"))

    def test_excluded_with_delivery(self):
        tax = calculate_tax(
            merchandise_subtotal="100.00",
            delivery_fee="5.00",
            enabled=True,
            pricing_mode=TaxPricingMode.EXCLUDED,
            rate_percent_value="15",
        )
        self.assertEqual(tax.tax_amount, Decimal("15.00"))
        self.assertEqual(tax.total, Decimal("120.00"))

    def test_included_with_delivery(self):
        tax = calculate_tax(
            merchandise_subtotal="115.00",
            delivery_fee="5.00",
            enabled=True,
            pricing_mode=TaxPricingMode.INCLUDED,
            rate_percent_value="15",
        )
        self.assertEqual(tax.tax_amount, Decimal("15.00"))
        self.assertEqual(tax.total, Decimal("120.00"))


class MarketplaceTaxSettingsTests(TestCase):
    def test_tax_rate_validation(self):
        settings_obj, _ = MarketplaceSettings.objects.update_or_create(
            pk=1,
            defaults={
                "currency": MarketplaceCurrency.ZAR,
                "tax_enabled": True,
                "tax_pricing_mode": TaxPricingMode.EXCLUDED,
                "tax_rate": Decimal("15"),
            },
        )
        settings_obj.tax_rate = Decimal("-1")
        with self.assertRaises(ValidationError):
            settings_obj.full_clean()
        settings_obj.tax_rate = Decimal("100.01")
        with self.assertRaises(ValidationError):
            settings_obj.full_clean()


@override_settings(
    PAYSTACK_PUBLIC_KEY="pk_test_x",
    PAYSTACK_SECRET_KEY="sk_test_x",
    PAYSTACK_CURRENCY="ZAR",
    MARKETPLACE_DELIVERY_FEE="5.00",
)
class CheckoutTaxIntegrationTests(TestCase):
    def setUp(self):
        MarketplaceSettings.objects.update_or_create(
            pk=1,
            defaults={
                "currency": MarketplaceCurrency.ZAR,
                "tax_enabled": True,
                "tax_pricing_mode": TaxPricingMode.EXCLUDED,
                "tax_rate": Decimal("15.0000"),
            },
        )
        self.user = User.objects.create_user(
            username="taxbuyer",
            email="taxbuyer@example.com",
            password="pass12345",
        )
        self.category = Category.objects.create(name="Tax Shop", slug="tax-shop")
        self.business = Business.objects.create(name="Tax Maker", slug="tax-maker")
        self.product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Taxable Product",
            slug="taxable-product",
            status=Product.ProductStatus.PUBLISHED,
            marketplace_enabled=True,
        )
        self.variant = add_sellable_variant(
            self.product,
            price="100.00",
            quantity=10,
            stock_mode=VariantOffer.StockMode.TRACKED,
        )
        self.cart = Cart.objects.create(
            user=self.user,
            token=__import__("uuid").uuid4(),
            last_activity_at=timezone.now(),
        )
        CartItem.objects.create(
            cart=self.cart,
            variant=self.variant,
            quantity=1,
            price_snapshot=Decimal("100.00"),
        )

    def _ready_checkout(self):
        checkout = get_or_start_checkout(self.user)
        update_customer(
            checkout,
            name="Tax Buyer",
            email="taxbuyer@example.com",
            phone="+263771111111",
        )
        update_fulfilment(checkout, method=FulfilmentMethod.COLLECTION)
        checkout.payment_provider = PaymentProvider.PAYSTACK
        checkout.terms_accepted_at = timezone.now()
        checkout.save()
        return checkout

    def test_checkout_totals_excluded(self):
        checkout = get_or_start_checkout(self.user)
        totals = checkout_totals(checkout)
        self.assertEqual(totals["subtotal"], Decimal("100.00"))
        self.assertEqual(totals["tax_amount"], Decimal("15.00"))
        self.assertEqual(totals["total"], Decimal("115.00"))

    def test_checkout_totals_included(self):
        MarketplaceSettings.objects.filter(pk=1).update(
            tax_pricing_mode=TaxPricingMode.INCLUDED,
        )
        checkout = get_or_start_checkout(self.user)
        totals = checkout_totals(checkout)
        self.assertEqual(totals["tax_amount"], Decimal("13.04"))
        self.assertEqual(totals["total"], Decimal("100.00"))

    def test_checkout_totals_disabled(self):
        MarketplaceSettings.objects.filter(pk=1).update(tax_enabled=False)
        checkout = get_or_start_checkout(self.user)
        totals = checkout_totals(checkout)
        self.assertFalse(totals["tax_enabled"])
        self.assertEqual(totals["tax_amount"], Decimal("0.00"))
        self.assertEqual(totals["total"], Decimal("100.00"))

    @patch.object(paystack, "initialize_transaction")
    def test_place_order_uses_taxed_paystack_amount(self, mock_init):
        mock_init.return_value = {
            "authorization_url": "https://checkout.paystack.com/tax",
            "access_code": "taxcode",
        }
        checkout = self._ready_checkout()
        place_order(
            checkout,
            callback_url="http://testserver/marketplace/checkout/payment/callback/",
        )
        mock_init.assert_called_once()
        self.assertEqual(mock_init.call_args.kwargs["amount_cents"], 11500)
        checkout.refresh_from_db()
        self.assertEqual(checkout.tax_amount, Decimal("15.00"))
        self.assertEqual(checkout.total_payable, Decimal("115.00"))
        self.assertTrue(checkout.tax_enabled)

    @patch.object(paystack, "verify_transaction")
    def test_order_snapshot_survives_settings_change(self, mock_verify):
        mock_verify.return_value = {
            "status": "success",
            "amount": 11500,
            "currency": "ZAR",
            "customer": {"email": "taxbuyer@example.com"},
        }
        checkout = self._ready_checkout()
        tax = calculate_tax(
            merchandise_subtotal="100.00",
            delivery_fee="0",
            enabled=True,
            pricing_mode=TaxPricingMode.EXCLUDED,
            rate_percent_value="15",
            currency="ZAR",
        )
        from marketplace.checkout.checkout_workflow import _freeze_tax_on_checkout

        _freeze_tax_on_checkout(checkout, tax)
        checkout.payment_reference = "sim-tax-snap"
        checkout.payment_status = PaymentStatus.PENDING
        checkout.save()
        from inventory.services import reserve_stock

        reserve_stock(self.variant, 1)
        checkout.stock_reservations.create(variant=self.variant, quantity=1)

        order = apply_paystack_success("sim-tax-snap")
        self.assertEqual(order.tax_amount, Decimal("15.00"))
        self.assertEqual(order.tax_rate, Decimal("15.0000"))
        self.assertEqual(order.total, Decimal("115.00"))

        MarketplaceSettings.objects.filter(pk=1).update(
            tax_rate=Decimal("20.0000"),
            tax_pricing_mode=TaxPricingMode.INCLUDED,
        )
        order.refresh_from_db()
        self.assertEqual(order.tax_amount, Decimal("15.00"))
        self.assertEqual(order.tax_rate, Decimal("15.0000"))
        self.assertEqual(order.tax_pricing_mode, TaxPricingMode.EXCLUDED)

    @patch.object(paystack, "verify_transaction")
    def test_amount_mismatch_fails(self, mock_verify):
        mock_verify.return_value = {
            "status": "success",
            "amount": 9999,
            "currency": "ZAR",
            "customer": {"email": "taxbuyer@example.com"},
        }
        checkout = self._ready_checkout()
        tax = calculate_tax(
            merchandise_subtotal="100.00",
            enabled=True,
            pricing_mode=TaxPricingMode.EXCLUDED,
            rate_percent_value="15",
            currency="ZAR",
        )
        from marketplace.checkout.checkout_workflow import _freeze_tax_on_checkout

        _freeze_tax_on_checkout(checkout, tax)
        checkout.payment_reference = "sim-tax-mismatch"
        checkout.payment_status = PaymentStatus.PENDING
        checkout.save()
        with self.assertRaises(Exception):
            apply_paystack_success("sim-tax-mismatch")
        checkout.refresh_from_db()
        self.assertEqual(checkout.payment_status, PaymentStatus.FAILED)
        self.assertFalse(Order.objects.filter(user=self.user).exists())

    def test_finish_paid_copies_tax_snapshot(self):
        checkout = self._ready_checkout()
        tax = calculate_tax(
            merchandise_subtotal="100.00",
            enabled=True,
            pricing_mode=TaxPricingMode.EXCLUDED,
            rate_percent_value="15",
            currency="ZAR",
        )
        from marketplace.checkout.checkout_workflow import _freeze_tax_on_checkout

        _freeze_tax_on_checkout(checkout, tax)
        checkout.payment_status = PaymentStatus.PAID
        checkout.paid_at = timezone.now()
        checkout.save()
        order = finish_paid_checkout(checkout)
        self.assertEqual(order.tax_amount, Decimal("15.00"))
        self.assertEqual(order.currency, "ZAR")
        self.assertEqual(order.total, Decimal("115.00"))
