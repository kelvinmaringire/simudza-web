from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.db.models import F

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


def _inventory_for_update(variant):
    return Inventory.objects.select_for_update().get(variant=variant)


@transaction.atomic
def reserve_stock(variant, quantity):
    """Increase reserved_quantity if enough units are available."""
    if quantity <= 0:
        return
    inventory = _inventory_for_update(variant)
    available = inventory.quantity - inventory.reserved_quantity
    if quantity > available:
        raise ValidationError(
            f"Not enough stock for {variant.label} (only {available} available)."
        )
    inventory.reserved_quantity = F("reserved_quantity") + quantity
    inventory.save(update_fields=["reserved_quantity", "updated_at"])
    inventory.refresh_from_db(fields=["reserved_quantity", "quantity"])


@transaction.atomic
def release_stock(variant, quantity):
    """Lower reserved_quantity after a cancelled or failed checkout."""
    if quantity <= 0:
        return
    inventory = _inventory_for_update(variant)
    if quantity > inventory.reserved_quantity:
        quantity = inventory.reserved_quantity
    if quantity <= 0:
        return
    inventory.reserved_quantity = F("reserved_quantity") - quantity
    inventory.save(update_fields=["reserved_quantity", "updated_at"])


@transaction.atomic
def commit_stock(variant, quantity):
    """Fulfill a paid order: reduce on-hand and reserved quantities."""
    if quantity <= 0:
        return
    inventory = _inventory_for_update(variant)
    if quantity > inventory.reserved_quantity:
        raise ValidationError(
            f"Cannot commit {quantity} units; only {inventory.reserved_quantity} reserved."
        )
    if quantity > inventory.quantity:
        raise ValidationError("Cannot commit more than on-hand quantity.")
    inventory.quantity = F("quantity") - quantity
    inventory.reserved_quantity = F("reserved_quantity") - quantity
    inventory.save(update_fields=["quantity", "reserved_quantity", "updated_at"])
