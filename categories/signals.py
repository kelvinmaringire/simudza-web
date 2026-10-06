from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Category


@receiver(pre_save, sender=Category)
def category_capture_quality_fields(sender, instance, raw=False, **kwargs):
    if raw or not instance.pk:
        return
    from products.quality import CATEGORY_QUALITY_FIELDS

    instance._quality_fields_before = (
        Category.objects.filter(pk=instance.pk)
        .values(*CATEGORY_QUALITY_FIELDS)
        .first()
    )


@receiver(post_save, sender=Category)
def category_quality_on_save(sender, instance, created=False, raw=False, **kwargs):
    if raw or created:
        return
    from products.quality import CATEGORY_QUALITY_FIELDS

    before = getattr(instance, "_quality_fields_before", None)
    if before is not None and all(
        before[field] == getattr(instance, field) for field in CATEGORY_QUALITY_FIELDS
    ):
        return

    def _refresh_products():
        from products.models import Product
        from products.quality import refresh_product_quality

        refresh_product_quality(Product.objects.filter(category_id=instance.pk))

    transaction.on_commit(_refresh_products, robust=True)
