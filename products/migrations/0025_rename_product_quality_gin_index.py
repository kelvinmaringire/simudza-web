from django.contrib.postgres.indexes import GinIndex
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0024_product_data_quality"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="product",
            name="products_product_quality_issues",
        ),
        migrations.AddIndex(
            model_name="product",
            index=GinIndex(
                fields=["quality_issues"],
                name="product_quality_issues_gin",
            ),
        ),
    ]
