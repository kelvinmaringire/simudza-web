from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from businesses.models import Business
from categories.models import Category
from products.models import Product, ProductVariant
from products.views import ProductDetailView, build_gallery


class BuildGalleryTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user("g", "g@x.com", "pass")
        business = Business.objects.create(
            name="Co",
            slug="co",
            owner=owner,
            verified_at=timezone.now(),
        )
        self.product = Product.objects.create(
            business=business,
            category=Category.objects.create(name="Drinks", slug="drinks"),
            name="Mazoe",
            slug="mazoe-gallery",
            status=Product.ProductStatus.PUBLISHED,
            verified_at=timezone.now(),
        )
        self.orange = ProductVariant.objects.create(
            product=self.product,
            name="Orange Crush",
            sort_order=1,
            size_value=Decimal("2"),
            size_unit="L",
        )
        self.raspberry = ProductVariant.objects.create(
            product=self.product,
            name="Raspberry",
            sort_order=2,
            size_value=Decimal("2"),
            size_unit="L",
        )

    def test_gallery_lists_variant_images_before_product_images(self):
        gallery = build_gallery(self.product, [self.orange, self.raspberry])
        self.assertEqual(len(gallery), 0)


class ProductDetailVariantPageTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user("v", "v@x.com", "pass")
        business = Business.objects.create(
            name="Mazoe Co",
            slug="mazoe-co",
            owner=owner,
            verified_at=timezone.now(),
        )
        self.product = Product.objects.create(
            business=business,
            category=Category.objects.create(name="Drinks", slug="drinks-v"),
            name="Mazoe",
            slug="mazoe-variants",
            status=Product.ProductStatus.PUBLISHED,
            verified_at=timezone.now(),
        )
        self.first = ProductVariant.objects.create(
            product=self.product,
            name="Orange Crush",
            sort_order=1,
            size_value=Decimal("2"),
            size_unit="L",
            packaging="Bottle",
        )
        self.second = ProductVariant.objects.create(
            product=self.product,
            name="Raspberry",
            sort_order=2,
            size_value=Decimal("2"),
            size_unit="L",
        )
        self.url = self.product.get_absolute_url()

    def test_default_selects_first_variant(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_variant"], self.first)

    def test_query_param_selects_variant(self):
        response = self.client.get(self.url, {"variant": self.second.pk})
        self.assertEqual(response.context["selected_variant"], self.second)
        self.assertContains(response, f'id="variant-option-{self.second.pk}"')
        self.assertContains(response, "checked")

    def test_invalid_variant_falls_back_to_first(self):
        response = self.client.get(self.url, {"variant": "nope"})
        self.assertEqual(response.context["selected_variant"], self.first)

    def test_renders_option_radios_not_variants_table(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'name="variant"')
        self.assertContains(response, "Orange Crush")
        self.assertContains(response, "Raspberry")
        self.assertNotContains(response, "<th>Option</th>")

    def test_initial_image_index_for_selected_variant(self):
        view = ProductDetailView()
        view.request = type("R", (), {"GET": {"variant": str(self.second.pk)}})()
        ctx = view.get_variant_context(self.product)
        self.assertEqual(ctx["selected_variant"], self.second)
