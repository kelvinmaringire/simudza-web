from django.contrib.auth import get_user_model
from django.test import TestCase

from businesses.models import Business
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
            "country_of_origin": "Zimbabwe",
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
