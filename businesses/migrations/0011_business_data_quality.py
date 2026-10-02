from django.contrib.postgres.indexes import GinIndex
from django.db import migrations, models


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
    ]
