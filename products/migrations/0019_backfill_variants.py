from django.db import migrations


def _variant_name(size_value, size_unit):
    if size_value is None and not size_unit:
        return "Standard"
    value = ""
    if size_value is not None:
        value = format(size_value, "f").rstrip("0").rstrip(".")
    unit = size_unit or ""
    label = f"{value} {unit}".strip()
    return label or "Standard"


def backfill_variants(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ProductVariant = apps.get_model("products", "ProductVariant")
    for product in Product.objects.all().iterator():
        if ProductVariant.objects.filter(product_id=product.pk).exists():
            continue
        ProductVariant.objects.create(
            product_id=product.pk,
            name=_variant_name(product.size_value, product.size_unit),
            sku=product.sku or "",
            barcode=product.barcode or "",
            size_value=product.size_value,
            size_unit=product.size_unit or "",
            price=product.price,
            sort_order=0,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0018_productvariant"),
    ]

    operations = [
        migrations.RunPython(backfill_variants, migrations.RunPython.noop),
    ]
