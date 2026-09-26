from django.db import migrations


def _next_child_path(page_model, parent):
    last_child = (
        page_model.objects.filter(path__startswith=parent.path, depth=parent.depth + 1)
        .order_by("-path")
        .first()
    )
    if last_child is None:
        return f"{parent.path}0001"
    return f"{last_child.path[:-4]}{int(last_child.path[-4:]) + 1:04d}"


def create_product_classification_page(apps, schema_editor):
    # Historical models only — avoid live add_child(), which triggers Wagtail
    # search indexing before wagtailsearch_indexentry exists on fresh migrates.
    ContentType = apps.get_model("contenttypes", "ContentType")
    Page = apps.get_model("wagtailcore", "Page")
    HomePage = apps.get_model("home", "HomePage")
    ProductClassificationPage = apps.get_model(
        "products",
        "ProductClassificationPage",
    )

    home = HomePage.objects.order_by("path").first()
    if home is None or ProductClassificationPage.objects.exists():
        return

    content_type, _ = ContentType.objects.get_or_create(
        model="productclassificationpage",
        app_label="products",
    )
    path = _next_child_path(Page, home)

    ProductClassificationPage.objects.create(
        title="How Simudza Classifies Zimbabwean Products",
        draft_title="How Simudza Classifies Zimbabwean Products",
        slug="product-classification",
        content_type=content_type,
        locale_id=home.locale_id,
        path=path,
        depth=home.depth + 1,
        numchild=0,
        url_path=f"{home.url_path}product-classification/",
        live=True,
    )
    HomePage.objects.filter(pk=home.pk).update(numchild=home.numchild + 1)


def remove_product_classification_page(apps, schema_editor):
    ProductClassificationPage = apps.get_model(
        "products",
        "ProductClassificationPage",
    )
    HomePage = apps.get_model("home", "HomePage")

    deleted, _ = ProductClassificationPage.objects.filter(
        slug="product-classification",
    ).delete()
    if deleted:
        home = HomePage.objects.order_by("path").first()
        if home is not None and home.numchild > 0:
            HomePage.objects.filter(pk=home.pk).update(numchild=home.numchild - 1)


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0008_productclassificationpage"),
        ("home", "0002_create_homepage"),
    ]

    operations = [
        migrations.RunPython(
            create_product_classification_page,
            remove_product_classification_page,
        ),
    ]
