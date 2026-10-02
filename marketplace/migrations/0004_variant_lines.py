import django.db.models.deletion
from django.db import migrations, models


def backfill_cart_and_order_items(apps, schema_editor):
    CartItem = apps.get_model("marketplace", "CartItem")
    OrderItem = apps.get_model("marketplace", "OrderItem")
    ProductVariant = apps.get_model("products", "ProductVariant")

    for item in CartItem.objects.all().iterator():
        variant = (
            ProductVariant.objects.filter(product_id=item.product_id)
            .order_by("sort_order", "pk")
            .first()
        )
        if variant is None:
            item.delete()
            continue
        item.variant_id = variant.pk
        item.save(update_fields=["variant_id"])

    for item in OrderItem.objects.all().iterator():
        if item.product_id is None:
            continue
        variant = (
            ProductVariant.objects.filter(product_id=item.product_id)
            .order_by("sort_order", "pk")
            .first()
        )
        item.variant_id = variant.pk if variant else None
        if variant:
            name = variant.name or "Standard"
            if not variant.name and (variant.size_value or variant.size_unit):
                value = ""
                if variant.size_value is not None:
                    value = format(variant.size_value, "f").rstrip("0").rstrip(".")
                unit = variant.size_unit or ""
                name = f"{value} {unit}".strip() or "Standard"
            item.variant_label = name
        item.save(update_fields=["variant_id", "variant_label"])


class Migration(migrations.Migration):

    dependencies = [
        ("marketplace", "0003_create_marketplace_page"),
        ("products", "0019_backfill_variants"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="variant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="order_items",
                to="products.productvariant",
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="variant_label",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="cartitem",
            name="variant",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cart_items",
                to="products.productvariant",
            ),
        ),
        migrations.RunPython(backfill_cart_and_order_items, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="cartitem",
            name="unique_cart_product",
        ),
        migrations.RemoveField(
            model_name="cartitem",
            name="product",
        ),
        migrations.AlterField(
            model_name="cartitem",
            name="variant",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cart_items",
                to="products.productvariant",
            ),
        ),
        migrations.AddConstraint(
            model_name="cartitem",
            constraint=models.UniqueConstraint(
                fields=("cart", "variant"),
                name="unique_cart_variant",
            ),
        ),
    ]
