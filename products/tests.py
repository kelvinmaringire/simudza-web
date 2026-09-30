from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from businesses.models import Business
from businesses.verification import FreshnessTier
from categories.models import Category
from products.forms import ProductForm, unique_product_slug
from products.models import Product


class UniqueProductSlugTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(
            "slug-owner",
            "slug-owner@example.com",
            "pass",
        )
        self.business = Business.objects.create(
            name="Slug Biz",
            slug="slug-biz",
            owner=owner,
        )
        self.category = Category.objects.create(
            name="Slug Cat",
            slug="slug-cat",
        )

    def test_unique_product_slug_appends_suffix_on_collision(self):
        Product.objects.create(
            business=self.business,
            category=self.category,
            name="Widget",
            slug="widget",
        )
        self.assertEqual(unique_product_slug("Widget"), "widget-2")

    def test_unique_product_slug_excludes_self(self):
        product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Widget",
            slug="widget",
        )
        self.assertEqual(
            unique_product_slug("Widget", exclude_pk=product.pk),
            "widget",
        )


class ProductSlugStabilityTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(
            "product-owner",
            "product-owner@example.com",
            "pass",
        )
        self.business = Business.objects.create(
            name="Acme",
            slug="acme",
            owner=owner,
        )
        self.category = Category.objects.create(
            name="Food",
            slug="food",
        )
        self.user = owner

    def _form_data(self, **overrides):
        data = {
            "business": self.business.pk,
            "name": "Original Name",
            "short_description": "",
            "description": "",
            "category": self.category.pk,
            "origin_type": Product.OriginType.MADE_IN_ZIMBABWE,
            "brand_name": "",
            "sku": "",
            "barcode": "",
            "size_value": "",
            "size_unit": "",
            "price": "",
            "status": Product.ProductStatus.PUBLISHED,
            "featured": False,
            "verified_at": "",
        }
        data.update(overrides)
        return data

    def test_create_sets_slug_from_name(self):
        form = ProductForm(data=self._form_data(), for_user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()
        self.assertEqual(product.slug, "original-name")

    def test_published_rename_keeps_slug(self):
        product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Original Name",
            slug="original-name",
            status=Product.ProductStatus.PUBLISHED,
        )
        form = ProductForm(
            data=self._form_data(name="Brand New Title"),
            instance=product,
            for_user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()
        self.assertEqual(product.name, "Brand New Title")
        self.assertEqual(product.slug, "original-name")

    def test_draft_rename_updates_slug(self):
        product = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Draft Item",
            slug="draft-item",
            status=Product.ProductStatus.DRAFT,
        )
        form = ProductForm(
            data=self._form_data(
                name="Renamed Draft",
                status=Product.ProductStatus.DRAFT,
            ),
            instance=product,
            for_user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()
        self.assertEqual(product.slug, "renamed-draft")


class ProductVisibleInSearchTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user("vis", "vis@x.com", "pass")
        self.category = Category.objects.create(name="Vis", slug="vis")
        self.business = Business.objects.create(
            name="Vis Biz",
            slug="vis-biz",
            owner=owner,
            verified_at=timezone.now(),
        )

    def test_visible_in_search_excludes_hidden_by_age(self):
        fresh = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Fresh",
            slug="fresh-vis",
            verified_at=timezone.now(),
        )
        hidden = Product.objects.create(
            business=self.business,
            category=self.category,
            name="Hidden",
            slug="hidden-vis",
            verified_at=timezone.now() - timedelta(days=366),
        )
        visible_ids = set(Product.objects.visible_in_search().values_list("pk", flat=True))
        self.assertIn(fresh.pk, visible_ids)
        self.assertNotIn(hidden.pk, visible_ids)
        self.assertEqual(hidden.freshness.tier, FreshnessTier.HIDDEN)
