"""Variant selling terms (price, on sale) and the "can be bought now" rule."""

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Min

from products.models import ProductVariant

from .models import VariantOffer, sellable_variant_q


def ensure_offer(variant):
    """Create the offer row for a variant if one does not exist yet."""
    offer, _ = VariantOffer.objects.get_or_create(variant=variant)
    return offer


def set_variant_price(variant, price):
    offer = ensure_offer(variant)
    offer.price = price
    offer.save(update_fields=["price", "updated_at"])
    return offer


def price_for_variant(variant):
    try:
        return variant.offer.price
    except ObjectDoesNotExist:
        return None


def sellable_variants():
    return ProductVariant.objects.filter(sellable_variant_q()).select_related(
        "offer",
        "inventory",
    )


def with_sellable_variants(product_queryset):
    """Annotate ``from_price`` and ``sellable_variant_count``; keep products with one or more."""
    sellable = sellable_variant_q("variants__")
    return product_queryset.annotate(
        from_price=Min("variants__offer__price", filter=sellable),
        sellable_variant_count=Count("variants", filter=sellable, distinct=True),
    ).filter(sellable_variant_count__gt=0)


def product_has_sellable_variants(product):
    return sellable_variants().filter(product=product).exists()
