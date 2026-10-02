from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from reviews.models import BusinessReview

from .models import Business
from .quality import refresh_business_quality


def _refresh_business_and_products(business_pk):
    from products.quality import refresh_product_quality
    from products.models import Product

    refresh_business_quality(Business.objects.filter(pk=business_pk))
    refresh_product_quality(Product.objects.filter(business_id=business_pk))


@receiver(post_save, sender=Business)
def business_quality_on_save(sender, instance, raw=False, **kwargs):
    if raw:
        return
    transaction.on_commit(
        lambda: _refresh_business_and_products(instance.pk),
        robust=True,
    )


@receiver(post_save, sender=BusinessReview)
def business_review_quality_on_save(sender, instance, raw=False, **kwargs):
    if raw or not instance.business_id:
        return
    transaction.on_commit(
        lambda: _refresh_business_and_products(instance.business_id),
        robust=True,
    )
