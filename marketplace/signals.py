from django.db.models.signals import post_save
from django.dispatch import receiver

from products.models import ProductVariant

from .offers import ensure_offer


@receiver(post_save, sender=ProductVariant)
def create_offer_for_variant(sender, instance, raw=False, **kwargs):
    if raw:
        return
    ensure_offer(instance)
