from django.apps import AppConfig


class HistoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "history"
    verbose_name = "Change history"

    def ready(self):
        from . import signals  # noqa: F401
