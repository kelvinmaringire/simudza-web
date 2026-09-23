from django.db import migrations


def create_marketplace_page(apps, schema_editor):
    from home.models import HomePage
    from marketplace.models import MarketplacePage

    home = HomePage.objects.first()
    if home is None or MarketplacePage.objects.exists():
        return

    home.add_child(
        instance=MarketplacePage(
            title="Marketplace",
            draft_title="Marketplace",
            slug="marketplace",
            live=True,
        )
    )


def remove_marketplace_page(apps, schema_editor):
    from marketplace.models import MarketplacePage

    MarketplacePage.objects.filter(slug="marketplace").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("marketplace", "0002_marketplacepage"),
        ("home", "0002_create_homepage"),
    ]

    operations = [
        migrations.RunPython(create_marketplace_page, remove_marketplace_page),
    ]
