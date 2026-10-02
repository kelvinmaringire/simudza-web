from django.db import transaction
from django.db.models.signals import post_save

from businesses.models import Business
from products.models import Product, ProductImage, ProductVariant

from .models import DuplicateFlag
from .services import flag_business_duplicates, flag_product_duplicates


# Detection runs after commit so inline variants/images saved in the same
# admin transaction are included. robust=True: a detection failure is logged
# and never breaks the save that triggered it.
def _check_business(sender, instance, raw=False, **kwargs):
    if raw:
        return
    pk = instance.pk
    transaction.on_commit(lambda: flag_business_duplicates(pk), robust=True)


def _check_product(sender, instance, raw=False, **kwargs):
    if raw:
        return
    pk = instance.pk
    transaction.on_commit(lambda: flag_product_duplicates(pk), robust=True)


def _check_parent_product(sender, instance, raw=False, **kwargs):
    if raw or not instance.product_id:
        return
    pk = instance.product_id
    transaction.on_commit(lambda: flag_product_duplicates(pk), robust=True)


def _refresh_duplicate_pair(flag_pk):
    flag = DuplicateFlag.objects.filter(pk=flag_pk).first()
    if not flag:
        return
    from businesses.models import Business
    from businesses.quality import refresh_business_quality
    from products.models import Product
    from products.quality import refresh_product_quality

    if flag.kind == DuplicateFlag.Kind.BUSINESS:
        if flag.business_a_id:
            refresh_business_quality(Business.objects.filter(pk=flag.business_a_id))
        if flag.business_b_id:
            refresh_business_quality(Business.objects.filter(pk=flag.business_b_id))
    elif flag.kind == DuplicateFlag.Kind.PRODUCT:
        if flag.product_a_id:
            refresh_product_quality(Product.objects.filter(pk=flag.product_a_id))
        if flag.product_b_id:
            refresh_product_quality(Product.objects.filter(pk=flag.product_b_id))


def _check_duplicate_flag(sender, instance, raw=False, **kwargs):
    if raw:
        return
    pk = instance.pk
    transaction.on_commit(lambda: _refresh_duplicate_pair(pk), robust=True)


post_save.connect(_check_business, sender=Business, weak=False)
post_save.connect(_check_product, sender=Product, weak=False)
post_save.connect(_check_parent_product, sender=ProductVariant, weak=False)
post_save.connect(_check_parent_product, sender=ProductImage, weak=False)
post_save.connect(_check_duplicate_flag, sender=DuplicateFlag, weak=False)
