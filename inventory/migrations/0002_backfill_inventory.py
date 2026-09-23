from django.db import migrations


def backfill_inventory(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Inventory = apps.get_model("inventory", "Inventory")

    existing_product_ids = set(
        Inventory.objects.values_list("product_id", flat=True)
    )
    records = [
        Inventory(
            product_id=product_id,
            quantity=0,
            reserved_quantity=0,
            low_stock_threshold=5,
        )
        for product_id in Product.objects.values_list("pk", flat=True)
        if product_id not in existing_product_ids
    ]
    if records:
        Inventory.objects.bulk_create(records)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0001_initial"),
        ("products", "0003_product_clusterable_gallery"),
    ]

    operations = [
        migrations.RunPython(backfill_inventory, noop),
    ]
