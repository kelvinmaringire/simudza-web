from django.db import migrations


def ensure_variants_for_marketplace_products(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ProductVariant = apps.get_model("products", "ProductVariant")
    Inventory = apps.get_model("inventory", "Inventory")
    VariantOffer = apps.get_model("marketplace", "VariantOffer")

    for product in Product.objects.filter(marketplace_enabled=True).iterator():
        variant = product.variants.order_by("sort_order", "pk").first()
        if variant is None:
            variant = ProductVariant.objects.create(product=product, name="Standard")
        Inventory.objects.get_or_create(
            variant=variant,
            defaults={
                "quantity": 0,
                "reserved_quantity": 0,
                "low_stock_threshold": 5,
            },
        )
        VariantOffer.objects.get_or_create(variant=variant)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0032_product_marketplace_enabled"),
        ("inventory", "0005_move_sku_barcode"),
        ("marketplace", "0008_variantoffer_stock_mode"),
    ]

    operations = [
        migrations.RunPython(
            ensure_variants_for_marketplace_products,
            noop_reverse,
        ),
    ]
