import django.db.models.deletion
from django.db import migrations, models


def backfill_inventory_variant(apps, schema_editor):
    Inventory = apps.get_model("inventory", "Inventory")
    ProductVariant = apps.get_model("products", "ProductVariant")
    for row in Inventory.objects.select_related("product").all().iterator():
        variant = (
            ProductVariant.objects.filter(product_id=row.product_id)
            .order_by("sort_order", "pk")
            .first()
        )
        if variant is None:
            continue
        row.variant_id = variant.pk
        row.save(update_fields=["variant_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_backfill_inventory"),
        ("products", "0019_backfill_variants"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventory",
            name="variant",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="inventory",
                to="products.productvariant",
            ),
        ),
        migrations.RunPython(backfill_inventory_variant, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="inventory",
            name="product",
        ),
        migrations.AlterField(
            model_name="inventory",
            name="variant",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="inventory",
                to="products.productvariant",
            ),
        ),
        migrations.AlterModelOptions(
            name="inventory",
            options={
                "ordering": ["variant__product__name", "variant__sort_order"],
                "verbose_name_plural": "inventory",
            },
        ),
    ]
