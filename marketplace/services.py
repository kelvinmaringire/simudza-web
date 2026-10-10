from decimal import Decimal, InvalidOperation

from django.db.models import Count, F, Prefetch, Q

from businesses.models import Business
from categories.models import Category
from products.models import Product, ProductVariant

from .models import Cart, CartItem

SORT_OPTIONS = (
    ("featured", "Featured"),
    ("newest", "Newest"),
    ("price_asc", "Price: low to high"),
    ("price_desc", "Price: high to low"),
    ("name", "Name: A–Z"),
)

SORT_ORDERING = {
    "featured": ("-featured", "name"),
    "newest": ("-created_at", "name"),
    "price_asc": ("from_price", "name"),
    "price_desc": ("-from_price", "name"),
    "name": ("name",),
}

RELATED_PRODUCT_LIMIT = 8

SELLABLE_VARIANTS_PREFETCH = Prefetch(
    "variants",
    queryset=(
        ProductVariant.objects.sellable()
        .select_related("inventory")
        .order_by("sort_order", "pk")
    ),
    to_attr="sellable_variants_list",
)


def get_marketplace_products():
    """Published products with at least one sellable variant."""
    return (
        Product.objects.with_sellable_variants()
        .served()
        .select_related(
            "business",
            "category",
            "image",
        )
        .prefetch_related(SELLABLE_VARIANTS_PREFETCH)
        .distinct()
        .order_by("-featured", "name")
    )


def filter_marketplace_products(queryset, search_query):
    if not search_query:
        return queryset
    return queryset.filter(
        Q(name__icontains=search_query)
        | Q(brand_name__icontains=search_query)
        | Q(short_description__icontains=search_query)
        | Q(business__name__icontains=search_query)
        | Q(category__name__icontains=search_query)
        | Q(variants__sku__icontains=search_query)
    ).distinct()


def parse_price(value):
    try:
        price = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    return price if price >= 0 else None


def apply_marketplace_filters(queryset, filters):
    """filters: dict from MarketplaceFilterMixin.get_filters()."""
    if filters.get("category"):
        slug = filters["category"]
        queryset = queryset.filter(Q(category__slug=slug) | Q(category__parent__slug=slug))
    if filters.get("maker"):
        queryset = queryset.filter(business__slug=filters["maker"])
    if filters.get("origin"):
        queryset = queryset.filter(origin_type=filters["origin"])
    if filters.get("min_price") is not None:
        queryset = queryset.filter(from_price__gte=filters["min_price"])
    if filters.get("max_price") is not None:
        queryset = queryset.filter(from_price__lte=filters["max_price"])
    if filters.get("verified"):
        from businesses.verification.levels import TRUSTED_LEVELS

        queryset = queryset.filter(business__verification_level__in=TRUSTED_LEVELS)
    return queryset


def sort_marketplace_products(queryset, sort_key):
    return queryset.order_by(*SORT_ORDERING.get(sort_key, SORT_ORDERING["featured"]))


def _facet_counts(queryset, field):
    return {
        row[field]: row["count"]
        for row in queryset.order_by()
        .values(field)
        .annotate(count=Count("pk", distinct=True))
    }


def get_marketplace_categories(queryset):
    """Categories that currently have sellable products, with product counts."""
    counts = _facet_counts(queryset, "category_id")
    categories = list(
        Category.objects.filter(pk__in=counts.keys()).order_by("name")
    )
    for category in categories:
        category.marketplace_count = counts.get(category.pk, 0)
    return categories


def get_marketplace_makers(queryset):
    counts = _facet_counts(queryset, "business_id")
    makers = list(Business.objects.filter(pk__in=counts.keys()).order_by("name"))
    for maker in makers:
        maker.marketplace_count = counts.get(maker.pk, 0)
    return makers


def get_marketplace_origins(queryset):
    counts = _facet_counts(queryset, "origin_type")
    return [
        {"value": value, "label": label, "count": counts[value]}
        for value, label in Product.OriginType.choices
        if value in counts
    ]


def get_related_marketplace_products(product, limit=RELATED_PRODUCT_LIMIT):
    """Same maker first, then same category — only items that can be bought now."""
    base = get_marketplace_products().visible_in_search().exclude(pk=product.pk)
    related = list(base.filter(business_id=product.business_id)[:limit])
    if len(related) < limit and product.category_id:
        related += list(
            base.filter(category_id=product.category_id)
            .exclude(pk__in=[item.pk for item in related])[: limit - len(related)]
        )
    return related


def get_sellable_variants_for_product(product):
    return list(
        ProductVariant.objects.sellable()
        .filter(product=product)
        .select_related("inventory")
        .order_by("sort_order", "pk")
    )

