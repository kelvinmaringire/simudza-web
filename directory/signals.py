from django.db.models.signals import post_save
from django.dispatch import receiver

from products.models import Product

from .models import DirectoryListing


def ensure_directory_listing(product):
    """Create a directory listing for a product if one does not exist yet."""
    DirectoryListing.objects.get_or_create(
        product=product,
        defaults={
            "featured": False,
            "show_in_directory": True,
        },
    )


@receiver(post_save, sender=Product)
def create_directory_listing_for_product(sender, instance, created, **kwargs):
    ensure_directory_listing(instance)
