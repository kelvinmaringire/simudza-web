# Generated manually

from django.db import migrations


def backfill_directory_listings(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    DirectoryListing = apps.get_model("directory", "DirectoryListing")

    existing_product_ids = set(
        DirectoryListing.objects.values_list("product_id", flat=True)
    )
    listings = [
        DirectoryListing(
            product_id=product_id,
            featured=False,
            show_in_directory=True,
        )
        for product_id in Product.objects.values_list("pk", flat=True)
        if product_id not in existing_product_ids
    ]
    if listings:
        DirectoryListing.objects.bulk_create(listings)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("directory", "0002_simplify_directory_listing"),
        ("products", "0003_product_clusterable_gallery"),
    ]

    operations = [
        migrations.RunPython(backfill_directory_listings, noop),
    ]
