# Generated manually for universal verification levels

from django.db import migrations, models


def forwards_product_level(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    for product in Product.objects.all().iterator():
        source = getattr(product, "verification_source", "") or ""
        if source == "manufacturer":
            level = "verified_manufacturer"
        elif source == "staff":
            level = "simudza_checked"
        else:
            level = "unverified"
        product.verification_level = level
        product.save(update_fields=["verification_level"])


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0016_verification_provenance"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="verification_level",
            field=models.CharField(
                choices=[
                    ("verified_manufacturer", "Verified manufacturer"),
                    ("simudza_checked", "Simudza checked"),
                    ("verified_source", "Verified source"),
                    ("community_reported", "Community reported"),
                    ("unverified", "Unverified"),
                    ("discontinued", "Discontinued / withdrawn"),
                ],
                db_index=True,
                default="unverified",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="verification_reference",
            field=models.CharField(
                blank=True,
                help_text="Source name or URL when level is Verified source.",
                max_length=300,
            ),
        ),
        migrations.RunPython(forwards_product_level, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="product",
            name="verification_source",
        ),
    ]
