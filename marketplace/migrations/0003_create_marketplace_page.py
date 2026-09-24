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


def create_marketplace_page(apps, schema_editor):
    # Historical models only — avoid live add_child(), which triggers Wagtail
    # search indexing before wagtailsearch_indexentry exists on fresh migrates.
    ContentType = apps.get_model("contenttypes", "ContentType")
    Page = apps.get_model("wagtailcore", "Page")
    HomePage = apps.get_model("home", "HomePage")
    MarketplacePage = apps.get_model("marketplace", "MarketplacePage")

    home = HomePage.objects.order_by("path").first()
    if home is None or MarketplacePage.objects.exists():
        return

    content_type, _ = ContentType.objects.get_or_create(
        model="marketplacepage",
        app_label="marketplace",
    )
    path = _next_child_path(Page, home)

    MarketplacePage.objects.create(
        title="Marketplace",
        draft_title="Marketplace",
        slug="marketplace",
        content_type=content_type,
        locale_id=home.locale_id,
        path=path,
        depth=home.depth + 1,
        numchild=0,
        url_path=f"{home.url_path}marketplace/",
        live=True,
    )
    HomePage.objects.filter(pk=home.pk).update(numchild=home.numchild + 1)


def remove_marketplace_page(apps, schema_editor):
    MarketplacePage = apps.get_model("marketplace", "MarketplacePage")
    HomePage = apps.get_model("home", "HomePage")

    deleted, _ = MarketplacePage.objects.filter(slug="marketplace").delete()
    if deleted:
        home = HomePage.objects.order_by("path").first()
        if home is not None and home.numchild > 0:
            HomePage.objects.filter(pk=home.pk).update(numchild=home.numchild - 1)


class Migration(migrations.Migration):

    dependencies = [
        ("marketplace", "0002_marketplacepage"),
        ("home", "0002_create_homepage"),
    ]

    operations = [
        migrations.RunPython(create_marketplace_page, remove_marketplace_page),
    ]
