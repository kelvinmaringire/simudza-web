# Generated manually for universal verification levels

from django.db import migrations, models


def forwards_business_level(apps, schema_editor):
    Business = apps.get_model("businesses", "Business")
    for business in Business.objects.all().iterator():
        source = getattr(business, "verification_source", "") or ""
        status = getattr(business, "verification_status", "") or ""
        if status == "rejected":
            level = "discontinued"
        elif source == "manufacturer":
            level = "verified_manufacturer"
        elif source == "staff":
            level = "simudza_checked"
        else:
            level = "unverified"
        business.verification_level = level
        business.save(update_fields=["verification_level"])


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0008_verification_provenance"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
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
            model_name="business",
            name="verification_reference",
            field=models.CharField(
                blank=True,
                help_text="Source name or URL when level is Verified source.",
                max_length=300,
            ),
        ),
        migrations.RunPython(forwards_business_level, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="business",
            name="verification_source",
        ),
        migrations.RemoveField(
            model_name="business",
            name="verification_status",
        ),
    ]
