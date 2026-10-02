from decimal import Decimal

from inventory.models import Inventory
from products.models import ProductVariant
from products.services import upsert_default_variant


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
    """Create a variant with stock so marketplace and directory tests can use it."""
    variant = upsert_default_variant(
        product,
        sku=sku,
        barcode=barcode,
        size_value=size_value,
        size_unit=size_unit,
        price=Decimal(str(price)) if price is not None else None,
    )
    if name:
        variant.name = name
        variant.save(update_fields=["name"])
    Inventory.objects.filter(variant=variant).update(
        quantity=quantity,
        reserved_quantity=0,
    )
    return variant
