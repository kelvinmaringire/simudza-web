from django.contrib.auth import get_user_model
from django.test import TestCase

from businesses.models import Business
from categories.models import Category
from inventory.models import Inventory
from marketplace.models import VariantOffer
from products.models import Product, ProductVariant
from products.services import ensure_marketplace_participation, upsert_default_variant


class ProductVariantDomainTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user("var", "var@x.com", "pass")
        self.category = Category.objects.create(name="Var", slug="var")
        self.business = Business.objects.create(
            name="Var Biz",
            slug="var-biz",
            owner=owner,
        )
        self.product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Juice",
            slug="juice",
        )

    def test_inventory_created_when_variant_saved(self):
        variant = ProductVariant.objects.create(
            product=self.product,
            name="330 ml",
        )
        self.assertTrue(Inventory.objects.filter(variant=variant).exists())

    def test_upsert_default_variant_updates_first_variant(self):
        first = upsert_default_variant(self.product, packaging="Can")
        upsert_default_variant(self.product, packaging="PET bottle")
        self.product.refresh_from_db()
        variants = list(self.product.variants.order_by("pk"))
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0].pk, first.pk)
        self.assertEqual(variants[0].packaging, "PET bottle")

    def test_marketplace_enabled_creates_default_variant_offer_and_inventory(self):
        self.assertFalse(self.product.variants.exists())
        self.product.marketplace_enabled = True
        self.product.save()

        variant = self.product.variants.get()
        self.assertTrue(Inventory.objects.filter(variant=variant).exists())
        self.assertTrue(VariantOffer.objects.filter(variant=variant).exists())

    def test_ensure_marketplace_participation_noop_when_disabled(self):
        self.assertIsNone(ensure_marketplace_participation(self.product))
        self.assertFalse(self.product.variants.exists())
