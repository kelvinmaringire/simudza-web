from django.db.models.signals import post_save
from django.dispatch import receiver

from products.models import Product

from .models import Inventory


def ensure_inventory(product):
    """Create an inventory record for a product if one does not exist yet."""
    Inventory.objects.get_or_create(
        product=product,
        defaults={
            "quantity": 0,
            "reserved_quantity": 0,
            "low_stock_threshold": 5,
        },
    )


@receiver(post_save, sender=Product)
def create_inventory_for_product(sender, instance, created, **kwargs):
    ensure_inventory(instance)
