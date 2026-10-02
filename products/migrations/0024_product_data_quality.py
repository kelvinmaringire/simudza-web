from django.contrib.postgres.indexes import GinIndex
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0023_productvariant_productvariant_price_not_negative_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="quality_checked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="quality_issues",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="product",
            name="quality_score",
            field=models.PositiveSmallIntegerField(db_index=True, default=0),
        ),
        migrations.AddIndex(
            model_name="product",
            index=GinIndex(
                fields=["quality_issues"],
                name="products_product_quality_issues",
            ),
        ),
    ]
