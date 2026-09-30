import json
import uuid

from django.db import migrations

from home.streams import DEFAULT_HOME_BODY


def _with_block_ids(stream_data):
    return [
        {
            "type": block["type"],
            "value": block["value"],
            "id": str(uuid.uuid4()),
        }
        for block in stream_data
    ]


def seed_homepage_body(apps, schema_editor):
    HomePage = apps.get_model("home", "HomePage")
    Revision = apps.get_model("wagtailcore", "Revision")
    for page in HomePage.objects.all():
        if page.body:
            continue
        body = _with_block_ids(DEFAULT_HOME_BODY)
        page.body = body
        page.save(update_fields=["body"])

        # The editor loads the latest revision, so seed it too or the next
        # publish from the admin would wipe the hero.
        if page.latest_revision_id:
            revision = Revision.objects.get(pk=page.latest_revision_id)
            if not revision.content.get("body"):
                revision.content["body"] = json.dumps(body)
                revision.save(update_fields=["content"])


def clear_homepage_body(apps, schema_editor):
    HomePage = apps.get_model("home", "HomePage")
    HomePage.objects.update(body=[])


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0003_homepage_body"),
        ("wagtailcore", "0078_referenceindex"),
    ]

    operations = [
        migrations.RunPython(
            seed_homepage_body,
            clear_homepage_body,
        ),
    ]
