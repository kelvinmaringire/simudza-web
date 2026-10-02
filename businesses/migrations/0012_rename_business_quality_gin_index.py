from django.contrib.postgres.indexes import GinIndex
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0011_business_data_quality"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="business",
            name="businesses_business_quality_issues",
        ),
        migrations.AddIndex(
            model_name="business",
            index=GinIndex(
                fields=["quality_issues"],
                name="business_quality_issues_gin",
            ),
        ),
    ]
