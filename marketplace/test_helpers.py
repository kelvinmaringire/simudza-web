from decimal import Decimal

from inventory.models import Inventory
from inventory.services import set_variant_identifiers
from products.services import upsert_default_variant

from .offers import set_variant_price


def add_sellable_variant(
    product,
    *,
    price="10.00",
    quantity=10,
    sku="",
    barcode="",
    size_value=None,
    size_unit="",
    name="",
):
    """Create a priced variant with stock so marketplace and directory tests can use it."""
    variant = upsert_default_variant(
        product,
        size_value=size_value,
        size_unit=size_unit,
    )
    if name:
        variant.name = name
        variant.save(update_fields=["name"])
    set_variant_identifiers(variant, sku=sku, barcode=barcode)
    set_variant_price(variant, Decimal(str(price)) if price is not None else None)
    Inventory.objects.filter(variant=variant).update(
        quantity=quantity,
        reserved_quantity=0,
    )
    return variant
