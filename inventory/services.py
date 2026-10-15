from django.core.exceptions import ObjectDoesNotExist

from .models import Inventory


def ensure_inventory(variant):
    """Create an inventory record for a variant if one does not exist yet."""
    inventory, _ = Inventory.objects.get_or_create(
        variant=variant,
        defaults={
            "quantity": 0,
            "reserved_quantity": 0,
            "low_stock_threshold": 5,
        },
    )
    return inventory


def inventory_for_variant(variant):
    try:
        return variant.inventory
    except ObjectDoesNotExist:
        return None


def set_variant_identifiers(variant, *, sku="", barcode=""):
    """Set SKU and barcode for a variant; raises ValidationError on clashes."""
    inventory = ensure_inventory(variant)
    inventory.sku = sku or ""
    inventory.barcode = barcode or ""
    inventory.full_clean()
    inventory.save(update_fields=["sku", "barcode", "updated_at"])
    return inventory
