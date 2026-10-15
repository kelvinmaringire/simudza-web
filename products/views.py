from django.db.models import Prefetch, Q
from django.views.generic import DetailView

from marketplace.offers import product_has_sellable_variants

from .models import Product, ProductImage, ProductVariantImage

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
        return (
            Product.objects.served()
            .select_related(
                "business",
                "business__logo",
                "category",
                "image",
            )
            .prefetch_related(gallery, "videos")
            .order_by("name")
        )


def build_gallery(product, variants):
    """Variant images first (tagged by variant), then product gallery, deduplicated by image id."""
    gallery = []
    seen = set()

    def add(image, alt, variant_id=None):
        if image is None or image.pk in seen:
            return
        seen.add(image.pk)
        gallery.append({"image": image, "alt": alt, "variant_id": variant_id})

    for variant in variants:
        for item in variant.images.all():
            add(
                item.image,
                item.alt_text or f"{product.name} — {variant.label}",
                variant_id=variant.pk,
            )
    add(product.image, product.name, variant_id=None)
    for item in product.images.all():
        add(item.image, item.alt_text or product.name, variant_id=None)
    return gallery


class ProductDetailView(ProductQuerysetMixin, DetailView):
    """Public product detail used by the directory (not marketplace)."""

    model = Product
    context_object_name = "product"
    template_name = "products/product_detail.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return self.get_base_queryset()

    def get_variants(self, product):
        images = Prefetch(
            "images",
            queryset=ProductVariantImage.objects.select_related("image").order_by(
                "sort_order", "pk"
            ),
        )
        return list(
            product.variants.prefetch_related(images).order_by("sort_order", "pk")
        )

    def get_selected_variant(self, variants):
        wanted = self.request.GET.get("variant", "")
        for variant in variants:
            if str(variant.pk) == wanted:
                return variant
        return variants[0] if variants else None

    def get_variant_context(self, product):
        variants = self.get_variants(product)
        selected = self.get_selected_variant(variants)
        gallery = build_gallery(product, variants)

        image_index_by_variant = {}
        for index, item in enumerate(gallery):
            vid = item.get("variant_id")
            if vid is not None and vid not in image_index_by_variant:
                image_index_by_variant[vid] = index

        variant_options = []
        for variant in variants:
            own_images = list(variant.images.all())
            variant_options.append(
                {
                    "variant": variant,
                    "image_index": image_index_by_variant.get(variant.pk),
                    "swatch": own_images[0].image if own_images else None,
                }
            )

        initial_image_index = 0
        if selected and selected.pk in image_index_by_variant:
            initial_image_index = image_index_by_variant[selected.pk]

        return {
            "gallery": gallery,
            "variant_options": variant_options,
            "selected_variant": selected,
            "initial_image_index": initial_image_index,
        }

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
        context.update(self.get_variant_context(product))
        context["business"] = product.business
        context["in_marketplace"] = product_has_sellable_variants(product)
        context["videos"] = list(product.videos.all())
        context["related_products"] = self.get_related_products(product)
        return context
