import json

from django.db.models import Prefetch
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils.cache import patch_vary_headers
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from products.models import Product, ProductImage

from .models import MarketplacePage
from .services import (
    SORT_OPTIONS,
    SORT_ORDERING,
    apply_marketplace_filters,
    filter_marketplace_products,
    get_marketplace_categories,
    get_marketplace_makers,
    get_marketplace_origins,
    get_marketplace_products,
    get_related_marketplace_products,
    get_sellable_variants_for_product,
    parse_price,
    sort_marketplace_products,
)
from .cart_workflow import serialize_cart_lines, sync_cart

JSON_LD_ESCAPES = {ord("<"): "\\u003C", ord(">"): "\\u003E", ord("&"): "\\u0026"}


class MarketplaceProductQuerysetMixin:
    paginate_by = 24

    def get_search_query(self):
        return self.request.GET.get("q", "").strip()

    def get_filters(self):
        params = self.request.GET
        return {
            "category": params.get("category", "").strip(),
            "maker": params.get("maker", "").strip(),
            "origin": params.get("origin", "").strip(),
            "min_price": parse_price(params.get("min_price", "")),
            "max_price": parse_price(params.get("max_price", "")),
            "verified": params.get("verified") == "true",
        }

    def get_sort_key(self):
        sort = self.request.GET.get("sort", "").strip()
        return sort if sort in SORT_ORDERING else "featured"

    def get_queryset(self):
        qs = filter_marketplace_products(
            get_marketplace_products().visible_in_search(),
            self.get_search_query(),
        )
        qs = apply_marketplace_filters(qs, self.get_filters())
        return sort_marketplace_products(qs, self.get_sort_key())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.copy()
        query.pop("page", None)
        filters = self.get_filters()
        catalogue = get_marketplace_products().visible_in_search()
        context.update(
            {
                "q": self.get_search_query(),
                "filters": filters,
                "filters_active": bool(self.get_search_query())
                or any(value not in (None, "", False) for value in filters.values()),
                "categories": get_marketplace_categories(catalogue),
                "makers": get_marketplace_makers(catalogue),
                "origins": get_marketplace_origins(catalogue),
                "sort": self.get_sort_key(),
                "sort_options": SORT_OPTIONS,
                "filter_querystring": query.urlencode(),
                "marketplace_page": MarketplacePage.objects.live().public().first(),
            }
        )
        return context


class MarketplaceIndexView(MarketplaceProductQuerysetMixin, ListView):
    model = Product
    context_object_name = "products"
    template_name = "marketplace/marketplace_page.html"

    def is_results_request(self):
        headers = self.request.headers
        return bool(headers.get("HX-Request")) and not headers.get(
            "HX-History-Restore-Request"
        )

    def get_template_names(self):
        if self.is_results_request():
            return ["marketplace/partials/product_results.html"]
        return super().get_template_names()

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        patch_vary_headers(response, ("HX-Request",))
        return response


class MarketplaceResultsView(MarketplaceProductQuerysetMixin, ListView):
    model = Product
    context_object_name = "products"
    template_name = "marketplace/partials/product_results.html"


class MarketplaceProductDetailView(DetailView):
    """Shoppable product page. Directory product pages live in the products app."""

    model = Product
    context_object_name = "product"
    template_name = "marketplace/product_detail.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        gallery = Prefetch(
            "images",
            queryset=ProductImage.objects.select_related("image").order_by(
                "sort_order",
                "pk",
            ),
        )
        return (
            Product.objects.filter(status=Product.ProductStatus.PUBLISHED)
            .select_related(
                "business",
                "business__logo",
                "category",
                "category__parent",
                "image",
            )
            .prefetch_related(gallery)
        )

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        sellable_variants = get_sellable_variants_for_product(self.object)
        if not sellable_variants:
            return redirect(self.object.get_absolute_url())
        context = self.get_context_data(
            object=self.object,
            sellable_variants=sellable_variants,
        )
        return self.render_to_response(context)

    def get_gallery(self, product):
        gallery = []
        if product.image:
            gallery.append({"image": product.image, "alt": product.name})
        for item in product.images.all():
            if product.image and item.image_id == product.image_id:
                continue
            gallery.append({"image": item.image, "alt": item.alt_text or product.name})
        return gallery

    def get_json_ld(self, product, gallery, sellable_variants):
        offers = []
        for variant in sellable_variants:
            available = variant.inventory.available_quantity
            offer = {
                "@type": "Offer",
                "priceCurrency": "USD",
                "price": str(variant.price),
                "availability": (
                    "https://schema.org/InStock"
                    if available > 0
                    else "https://schema.org/OutOfStock"
                ),
            }
            if variant.sku:
                offer["sku"] = variant.sku
            if variant.barcode:
                offer["gtin"] = variant.barcode
            offers.append(offer)

        data = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product.name,
            "url": self.request.build_absolute_uri(product.get_marketplace_url()),
            "offers": offers,
        }
        if product.short_description or product.description:
            data["description"] = product.short_description or product.description
        if product.brand_name or product.business_id:
            data["brand"] = {
                "@type": "Brand",
                "name": product.brand_name or product.business.name,
            }
        if gallery:
            data["image"] = [
                self.request.build_absolute_uri(
                    item["image"].get_rendition("max-960x960").url
                )
                for item in gallery
            ]
        return mark_safe(json.dumps(data).translate(JSON_LD_ESCAPES))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        sellable_variants = kwargs.get("sellable_variants")
        if sellable_variants is None:
            sellable_variants = get_sellable_variants_for_product(product)
        selected = sellable_variants[0] if sellable_variants else None
        available_quantity = (
            selected.inventory.available_quantity if selected else 0
        )
        gallery = self.get_gallery(product)
        image_url = ""
        if product.image:
            image_url = product.image.get_rendition("fill-96x96").url
        variant_options = []
        for variant in sellable_variants:
            variant_options.append(
                {
                    "id": variant.pk,
                    "label": variant.label,
                    "price": str(variant.price),
                    "sizeDisplay": variant.size_display,
                    "packaging": variant.packaging,
                    "sku": variant.sku,
                    "barcode": variant.barcode,
                    "maxQty": variant.inventory.available_quantity,
                }
            )
        context.update(
            {
                "business": product.business,
                "gallery": gallery,
                "sellable_variants": sellable_variants,
                "variant_options_json": mark_safe(
                    json.dumps(variant_options).translate(JSON_LD_ESCAPES)
                ),
                "cart_image_url": image_url,
                "cart_product_name": product.name,
                "cart_product_url": product.get_marketplace_url(),
                "available_quantity": available_quantity,
                "in_stock": any(
                    v.inventory.available_quantity > 0 for v in sellable_variants
                ),
                "low_stock": bool(
                    selected
                    and available_quantity > 0
                    and selected.inventory.is_low_stock
                ),
                "related_products": get_related_marketplace_products(product),
                "product_json_ld": self.get_json_ld(
                    product,
                    gallery,
                    sellable_variants,
                ),
            }
        )
        return context


def _parse_sync_body(request):
    if request.content_type and "application/json" in request.content_type:
        try:
            data = json.loads(request.body.decode() or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    raw = request.POST.get("payload", "")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


@require_POST
def cart_sync(request):
    """Sync localStorage cart snapshot to cart sessions and analytics."""
    body = _parse_sync_body(request)
    token = body.get("token")
    items = body.get("items")
    if not token:
        return HttpResponse(status=400)
    if not isinstance(items, list):
        return HttpResponse(status=400)

    user = request.user if request.user.is_authenticated else None
    apply = body.get("apply", True)
    if not isinstance(apply, bool):
        apply = str(apply).lower() in ("1", "true", "yes")
    cart = sync_cart(token=token, user=user, items=items, apply=apply)

    if user:
        lines = serialize_cart_lines(cart) if cart else []
        return JsonResponse({"items": lines})

    return HttpResponse(status=204)
