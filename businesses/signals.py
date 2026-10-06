from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from reviews.models import BusinessReview

from .models import Business
from .quality import refresh_business_quality


def _refresh_business(business_pk):
    refresh_business_quality(Business.objects.filter(pk=business_pk))


def _refresh_business_and_products(business_pk):
    from products.models import Product
    from products.quality import refresh_product_quality

    _refresh_business(business_pk)
    refresh_product_quality(Product.objects.filter(business_id=business_pk))


@receiver(pre_save, sender=Business)
def business_capture_quality_fields(sender, instance, raw=False, **kwargs):
    if raw or not instance.pk:
        return
    from products.quality import BUSINESS_QUALITY_FIELDS

    instance._quality_fields_before = (
        Business.objects.filter(pk=instance.pk)
        .values(*BUSINESS_QUALITY_FIELDS)
        .first()
    )


@receiver(post_save, sender=Business)
def business_quality_on_save(sender, instance, created=False, raw=False, **kwargs):
    if raw:
        return
    from products.quality import BUSINESS_QUALITY_FIELDS

    pk = instance.pk
    before = getattr(instance, "_quality_fields_before", None)
    products_unaffected = created or (
        before is not None
        and all(
            before[field] == getattr(instance, field)
            for field in BUSINESS_QUALITY_FIELDS
        )
    )
    refresh = _refresh_business if products_unaffected else _refresh_business_and_products
    transaction.on_commit(lambda: refresh(pk), robust=True)


@receiver(post_save, sender=BusinessReview)
def business_review_quality_on_save(sender, instance, raw=False, **kwargs):
    if raw or not instance.business_id:
        return
    pk = instance.business_id
    transaction.on_commit(lambda: _refresh_business(pk), robust=True)
