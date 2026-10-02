from django.db.models.signals import post_save
from django.dispatch import receiver

from products.models import ProductVariant

from .models import Inventory


def ensure_inventory(variant):
    """Create an inventory record for a variant if one does not exist yet."""
    Inventory.objects.get_or_create(
        variant=variant,
        defaults={
            "quantity": 0,
            "reserved_quantity": 0,
            "low_stock_threshold": 5,
        },
    )


@receiver(post_save, sender=ProductVariant)
def create_inventory_for_variant(sender, instance, created, **kwargs):
    ensure_inventory(instance)
