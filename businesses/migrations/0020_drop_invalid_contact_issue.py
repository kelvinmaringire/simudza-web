from django.db import migrations

RETIRED_ISSUE = "invalid_contact"


def drop_retired_issue(apps, schema_editor):
    for app_label, model_name in (("businesses", "Business"), ("products", "Product")):
        Model = apps.get_model(app_label, model_name)
        rows = Model.objects.filter(quality_issues__contains=[RETIRED_ISSUE])
        for pk, issues in rows.values_list("pk", "quality_issues"):
            Model.objects.filter(pk=pk).update(
                quality_issues=[code for code in issues if code != RETIRED_ISSUE]
            )


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0019_verification_levels_and_lifecycle"),
        ("products", "0027_verification_levels_and_lifecycle"),
    ]

    operations = [
        migrations.RunPython(drop_retired_issue, migrations.RunPython.noop),
    ]
