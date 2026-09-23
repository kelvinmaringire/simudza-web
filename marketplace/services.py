from django.db.models import F, Q

from products.models import Product

from .models import Cart, CartItem


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
