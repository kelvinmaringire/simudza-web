import uuid

from django.db import migrations

from products.streams import DEFAULT_PRODUCT_CLASSIFICATION_BODY


def _with_block_ids(stream_data):
    return [
        {
            "type": block["type"],
            "value": block["value"],
            "id": str(uuid.uuid4()),
        }
        for block in stream_data
    ]


def seed_classification_body(apps, schema_editor):
    ProductClassificationPage = apps.get_model(
        "products",
        "ProductClassificationPage",
    )
    body = _with_block_ids(DEFAULT_PRODUCT_CLASSIFICATION_BODY)
    for page in ProductClassificationPage.objects.all():
        if page.body:
            continue
        page.body = body
        page.save(update_fields=["body"])


def clear_classification_body(apps, schema_editor):
    ProductClassificationPage = apps.get_model(
        "products",
        "ProductClassificationPage",
    )
    ProductClassificationPage.objects.update(body=[])


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0010_productclassificationpage_body"),
    ]

    operations = [
        migrations.RunPython(
            seed_classification_body,
            clear_classification_body,
        ),
    ]
