from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("history", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="changelog",
            name="source",
            field=models.CharField(
                choices=[
                    ("admin", "Admin"),
                    ("dashboard", "Dashboard"),
                    ("submission", "Submission"),
                    ("import", "Import"),
                    ("system", "System"),
                    ("web", "Web"),
                    ("bulk_edit", "Bulk edit"),
                ],
                db_index=True,
                default="web",
                max_length=20,
            ),
        ),
    ]
