from django.db.models.signals import post_save
from django.dispatch import receiver

from products.models import ProductVariant

from .services import ensure_inventory


@receiver(post_save, sender=ProductVariant)
def create_inventory_for_variant(sender, instance, created, **kwargs):
    ensure_inventory(instance)
