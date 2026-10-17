from decimal import Decimal

from django.test import TestCase

from businesses.models import Business
from categories.models import Category
from inventory.models import Inventory
from marketplace.models import Cart, CartEvent, CartItem, VariantOffer
from marketplace.offers import (
    product_has_sellable_variants,
    sellable_variants,
    set_variant_price,
    with_sellable_variants,
)
from marketplace.tests.helpers import add_sellable_variant
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
        self.assertEqual(offer.stock_mode, VariantOffer.StockMode.UNLIMITED)

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

    def test_sellable_requires_marketplace_enabled(self):
        variant = add_sellable_variant(self.product, price="5.00", quantity=3)
        self.product.marketplace_enabled = False
        self.product.save(update_fields=["marketplace_enabled", "updated_at"])
        self.assertFalse(sellable_variants().filter(pk=variant.pk).exists())

    def test_unlimited_sellable_with_zero_stock(self):
        variant = add_sellable_variant(
            self.product,
            price="5.00",
            quantity=0,
            stock_mode=VariantOffer.StockMode.UNLIMITED,
        )
        self.assertTrue(sellable_variants().filter(pk=variant.pk).exists())
