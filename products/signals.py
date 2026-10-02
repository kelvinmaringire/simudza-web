from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from reviews.models import ProductReview

from .models import Product, ProductImage, ProductVariant
from .quality import refresh_product_quality


def _refresh_product_pk(pk):
    refresh_product_quality(Product.objects.filter(pk=pk))


def _schedule_product_refresh(pk):
    transaction.on_commit(lambda: _refresh_product_pk(pk), robust=True)


@receiver(post_save, sender=Product)
def product_quality_on_save(sender, instance, raw=False, **kwargs):
    if raw:
        return
    _schedule_product_refresh(instance.pk)


@receiver(post_save, sender=ProductVariant)
@receiver(post_save, sender=ProductImage)
def product_child_quality_on_save(sender, instance, raw=False, **kwargs):
    if raw or not instance.product_id:
        return
    _schedule_product_refresh(instance.product_id)


@receiver(post_delete, sender=ProductVariant)
@receiver(post_delete, sender=ProductImage)
def product_child_quality_on_delete(sender, instance, **kwargs):
    if instance.product_id:
        _schedule_product_refresh(instance.product_id)


@receiver(post_save, sender=ProductReview)
def product_review_quality_on_save(sender, instance, raw=False, **kwargs):
    if raw or not instance.product_id:
        return
    _schedule_product_refresh(instance.product_id)
