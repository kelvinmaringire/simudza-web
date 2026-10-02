from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0019_backfill_variants"),
        ("inventory", "0003_inventory_variant"),
        ("marketplace", "0004_variant_lines"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="product",
            name="barcode",
        ),
        migrations.RemoveField(
            model_name="product",
            name="price",
        ),
        migrations.RemoveField(
            model_name="product",
            name="size_unit",
        ),
        migrations.RemoveField(
            model_name="product",
            name="size_value",
        ),
        migrations.RemoveField(
            model_name="product",
            name="sku",
        ),
    ]
