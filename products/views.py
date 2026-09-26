from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch, Q
from django.views.generic import DetailView

from businesses.models import RetailLocation

from .models import Product, ProductImage

RELATED_PRODUCT_LIMIT = 8


class ProductQuerysetMixin:
    """Shared queryset for public product pages."""

    def get_base_queryset(self):
        gallery = Prefetch(
            "images",
            queryset=ProductImage.objects.select_related("image").order_by(
                "sort_order",
                "pk",
            ),
        )
        retail = Prefetch(
            "business__retail_locations",
            queryset=RetailLocation.objects.filter(is_active=True).order_by(
                "town_or_city",
                "name",
            ),
        )
        return (
            Product.objects.filter(status=Product.ProductStatus.PUBLISHED)
            .select_related(
                "business",
                "business__logo",
                "category",
                "image",
                "inventory",
            )
            .prefetch_related(gallery, retail)
            .order_by("name")
        )


class ProductDetailView(ProductQuerysetMixin, DetailView):
    """Public product detail used by the directory (not marketplace)."""

    model = Product
    context_object_name = "product"
    template_name = "products/product_detail.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return self.get_base_queryset()

    def get_related_products(self, product):
        """Same maker/brand first, then same category — keeps discovery moving."""
        base = (
            self.get_base_queryset()
            .exclude(pk=product.pk)
            .select_related("business", "category", "image")
        )
        related = []
        seen = set()

        def take(queryset, limit):
            for item in queryset[:limit]:
                if item.pk in seen:
                    continue
                seen.add(item.pk)
                related.append(item)
                if len(related) >= RELATED_PRODUCT_LIMIT:
                    return True
            return False

        maker_q = Q(business_id=product.business_id)
        if product.brand_name:
            maker_q |= Q(brand_name__iexact=product.brand_name)
        if take(base.filter(maker_q).order_by("name"), RELATED_PRODUCT_LIMIT):
            return related

        if product.category_id:
            take(
                base.filter(category_id=product.category_id)
                .exclude(pk__in=seen)
                .order_by("name"),
                RELATED_PRODUCT_LIMIT - len(related),
            )
        return related

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        gallery = []
        if product.image:
            gallery.append(
                {
                    "image": product.image,
                    "alt": product.name,
                }
            )
        for item in product.images.all():
            if product.image and item.image_id == product.image_id:
                continue
            gallery.append(
                {
                    "image": item.image,
                    "alt": item.alt_text or product.name,
                }
            )
        context["gallery"] = gallery
        context["business"] = product.business
        inventory = None
        try:
            inventory = product.inventory
        except ObjectDoesNotExist:
            inventory = None
        context["in_marketplace"] = (
            product.price is not None
            and inventory is not None
            and inventory.available_quantity > 0
        )
        business = product.business
        context["retail_locations"] = (
            list(business.retail_locations.all()) if business else []
        )
        context["related_products"] = self.get_related_products(product)
        return context
