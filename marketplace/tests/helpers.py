from decimal import Decimal

from inventory.models import Inventory
from inventory.services import set_variant_identifiers
from marketplace.models import VariantOffer
from marketplace.offers import set_variant_price
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
    stock_mode=VariantOffer.StockMode.TRACKED,
    enable_marketplace=True,
):
    """Create a priced variant with stock (tracked by default)."""
    if enable_marketplace and not product.marketplace_enabled:
        product.marketplace_enabled = True
        product.save(update_fields=["marketplace_enabled", "updated_at"])
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
    VariantOffer.objects.filter(variant=variant).update(stock_mode=stock_mode)
    Inventory.objects.filter(variant=variant).update(
        quantity=quantity,
        reserved_quantity=0,
    )
    return variant
