from django.conf import settings
from django.db import transaction
from wagtail.models import Collection


def get_or_create_collection(name):
    """Top-level Wagtail collection by name, created under Root when missing."""
    with transaction.atomic():
        collection = (
            Collection.objects.filter(depth=2, name__iexact=name).order_by("path").first()
        )
        if collection is not None:
            return collection
        root = Collection.get_first_root_node()
        return root.add_child(name=name)


def business_logo_collection():
    return get_or_create_collection(settings.BUSINESS_LOGO_COLLECTION_NAME)
