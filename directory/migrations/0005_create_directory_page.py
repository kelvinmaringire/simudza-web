from django.db import migrations


def create_directory_page(apps, schema_editor):
    # Use concrete models so Wagtail tree methods (add_child) are available.
    from directory.models import DirectoryPage
    from home.models import HomePage

    home = HomePage.objects.first()
    if home is None or DirectoryPage.objects.exists():
        return

    home.add_child(
        instance=DirectoryPage(
            title="Directory",
            draft_title="Directory",
            slug="directory",
            live=True,
        )
    )


def remove_directory_page(apps, schema_editor):
    from directory.models import DirectoryPage

    DirectoryPage.objects.filter(slug="directory").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("directory", "0004_directory_page"),
        ("home", "0002_create_homepage"),
    ]

    operations = [
        migrations.RunPython(create_directory_page, remove_directory_page),
    ]
