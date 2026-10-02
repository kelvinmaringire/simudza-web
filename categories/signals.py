from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Category


@receiver(post_save, sender=Category)
def category_quality_on_save(sender, instance, raw=False, **kwargs):
    if raw:
        return

    def _refresh_products():
        from products.models import Product
        from products.quality import refresh_product_quality

        refresh_product_quality(Product.objects.filter(category_id=instance.pk))

    transaction.on_commit(_refresh_products, robust=True)
