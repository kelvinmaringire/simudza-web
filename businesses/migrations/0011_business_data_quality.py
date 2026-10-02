from django.contrib.postgres.indexes import GinIndex
from django.db import migrations, models


def backfill_quality(apps, schema_editor):
    from businesses.quality import refresh_business_quality
    from businesses.models import Business
    from products.models import Product
    from products.quality import refresh_product_quality

    refresh_business_quality(Business.objects.all())
    refresh_product_quality(Product.objects.all())


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0010_videos"),
        ("products", "0024_product_data_quality"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="quality_checked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="business",
            name="quality_issues",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="business",
            name="quality_score",
            field=models.PositiveSmallIntegerField(db_index=True, default=0),
        ),
        migrations.AddIndex(
            model_name="business",
            index=GinIndex(
                fields=["quality_issues"],
                name="businesses_business_quality_issues",
            ),
        ),
        migrations.RunPython(backfill_quality, migrations.RunPython.noop),
    ]
