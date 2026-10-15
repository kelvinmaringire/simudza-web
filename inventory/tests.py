from django.core.exceptions import ValidationError
from django.test import TestCase

from businesses.models import Business
from categories.models import Category
from inventory.models import Inventory
from inventory.services import set_variant_identifiers
from products.models import Product, ProductVariant


class InventoryIdentifierTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Inv", slug="inv")
        self.business = Business.objects.create(name="Inv Co", slug="inv-co")
        self.product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Juice",
            slug="juice",
        )
        self.can = ProductVariant.objects.create(product=self.product, name="Can")
        self.bottle = ProductVariant.objects.create(product=self.product, name="Bottle")

    def test_set_variant_identifiers_writes_inventory(self):
        set_variant_identifiers(self.can, sku="J-330", barcode="6001234567890")
        inventory = Inventory.objects.get(variant=self.can)
        self.assertEqual(inventory.sku, "J-330")
        self.assertEqual(inventory.barcode, "6001234567890")

    def test_sku_must_be_unique_within_a_product(self):
        set_variant_identifiers(self.can, sku="J-1")
        with self.assertRaises(ValidationError) as ctx:
            set_variant_identifiers(self.bottle, sku="J-1")
        self.assertIn("sku", ctx.exception.message_dict)

    def test_same_sku_allowed_on_another_product(self):
        other = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Tea",
            slug="tea",
        )
        tea = ProductVariant.objects.create(product=other, name="Box")
        set_variant_identifiers(self.can, sku="001")
        set_variant_identifiers(tea, sku="001")
        self.assertEqual(Inventory.objects.filter(sku="001").count(), 2)

    def test_barcode_must_be_unique(self):
        set_variant_identifiers(self.can, barcode="600111")
        with self.assertRaises(ValidationError):
            set_variant_identifiers(self.bottle, barcode="600111")
