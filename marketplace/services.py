from decimal import Decimal, InvalidOperation

from django.db.models import Count, F, Q

from businesses.models import Business
from categories.models import Category
from products.models import Product

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
    "price_asc": ("price", "name"),
    "price_desc": ("-price", "name"),
    "name": ("name",),
}

RELATED_PRODUCT_LIMIT = 8


def get_marketplace_products():
    """Published products with a price and available inventory."""
    return (
        Product.objects.filter(
            status=Product.ProductStatus.PUBLISHED,
            price__isnull=False,
            inventory__quantity__gt=F("inventory__reserved_quantity"),
        )
        .select_related(
            "business",
            "category",
            "image",
            "inventory",
        )
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
        queryset = queryset.filter(price__gte=filters["min_price"])
    if filters.get("max_price") is not None:
        queryset = queryset.filter(price__lte=filters["max_price"])
    if filters.get("verified"):
        queryset = queryset.filter(business__verification_status="verified")
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
        Category.objects.filter(pk__in=counts.keys()).order_by("sort_order", "name")
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
    base = get_marketplace_products().exclude(pk=product.pk)
    related = list(base.filter(business_id=product.business_id)[:limit])
    if len(related) < limit and product.category_id:
        related += list(
            base.filter(category_id=product.category_id)
            .exclude(pk__in=[item.pk for item in related])[: limit - len(related)]
        )
    return related


def get_user_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def get_cart_with_items(user):
    cart, _ = Cart.objects.prefetch_related(
        "items__product__image",
        "items__product__inventory",
    ).get_or_create(user=user)
    return cart


def sync_user_cart(user, items):
    """
    Quietly replace the user's DB cart to match client localStorage items.
    items: iterable of {"product_id": int, "quantity": int}
    """
    cart = get_user_cart(user)
    product_ids = [
        item["product_id"] for item in items if item.get("product_id")
    ]
    sellable = {
        product.pk: product
        for product in get_marketplace_products().filter(pk__in=product_ids)
    }

    wanted = {}
    for item in items:
        product_id = item.get("product_id")
        try:
            quantity = int(item.get("quantity", 0))
        except (TypeError, ValueError):
            quantity = 0
        if product_id not in sellable or quantity <= 0:
            continue
        available = sellable[product_id].inventory.available_quantity
        wanted[product_id] = min(quantity, available)

    existing = {row.product_id: row for row in cart.items.all()}

    for product_id, quantity in wanted.items():
        row = existing.pop(product_id, None)
        if row:
            if row.quantity != quantity:
                row.quantity = quantity
                row.save(update_fields=["quantity"])
        else:
            CartItem.objects.create(
                cart=cart,
                product=sellable[product_id],
                quantity=quantity,
            )

    if existing:
        CartItem.objects.filter(
            pk__in=[row.pk for row in existing.values()]
        ).delete()

    return cart
