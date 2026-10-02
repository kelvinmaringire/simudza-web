from django.apps import AppConfig


class BusinessesConfig(AppConfig):
    name = "businesses"

    def ready(self):
        from . import signals  # noqa: F401
