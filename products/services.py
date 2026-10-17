"""
This services.py file manages the default product variant in Simudza. It ensures
that when a product is saved through a workflow that supports a single variant,
the system updates the product's first variant or creates one if none exists.
"""

from .models import ProductVariant


def _variant_name_from_size(size_value, size_unit):
    if size_value is None and not size_unit:
        return "Standard"
    value = ""
    if size_value is not None:
        value = format(size_value, "f").rstrip("0").rstrip(".")
    unit = size_unit or ""
    label = f"{value} {unit}".strip()
    return label or "Standard"


def upsert_default_variant(
    product,
    *,
    size_value=None,
    size_unit="",
    packaging="",
):
    """
    Update the product's first variant, or create one if none exist.
    Used by owner product saves and other single-variant write paths.
    """
    variant = product.variants.order_by("sort_order", "pk").first()
    if variant is None:
        variant = ProductVariant(
            product=product,
            name=_variant_name_from_size(size_value, size_unit),
        )
    variant.size_value = size_value
    variant.size_unit = size_unit or ""
    variant.packaging = packaging or ""
    if not variant.name:
        variant.name = _variant_name_from_size(size_value, size_unit)
    variant.save()
    return variant


def ensure_marketplace_participation(product):
    """
    Marketplace lists (prices, inventory) are per-variant. When a product opts
    into the marketplace, ensure it has at least one variant so offer/inventory
    rows exist (created by variant post_save signals).
    """
    if not product.pk or not product.marketplace_enabled:
        return None
    existing = product.variants.order_by("sort_order", "pk").first()
    if existing is not None:
        return existing
    return upsert_default_variant(product)
