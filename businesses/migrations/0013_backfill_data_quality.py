from django.db import migrations


def backfill_quality(apps, schema_editor):
    # Live models select every current column, which breaks on fresh databases
    # once later migrations add fields; there is nothing to backfill there.
    if not (
        apps.get_model("businesses", "Business").objects.exists()
        or apps.get_model("products", "Product").objects.exists()
    ):
        return

    # Uses live models and quality checks, which read duplicates, reviews and
    # inventory tables — every app touched must be listed in dependencies.
    from businesses.models import Business
    from businesses.quality import refresh_business_quality
    from products.models import Product
    from products.quality import refresh_product_quality

    refresh_business_quality(Business.objects.all())
    refresh_product_quality(Product.objects.all())


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0012_rename_business_quality_gin_index"),
        ("products", "0025_rename_product_quality_gin_index"),
        ("duplicates", "0001_initial"),
        ("reviews", "0002_listing_reports"),
        ("inventory", "0004_inventory_inventory_reserved_not_above_quantity"),
        ("history", "0002_changelog_bulk_edit_source"),
    ]

    operations = [
        migrations.RunPython(backfill_quality, migrations.RunPython.noop),
    ]
