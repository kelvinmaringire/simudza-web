from django.apps import AppConfig


class DuplicatesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "duplicates"
    verbose_name = "Duplicate detection"

    def ready(self):
        from . import signals  # noqa: F401
