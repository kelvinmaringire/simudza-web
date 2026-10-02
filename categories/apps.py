from django.apps import AppConfig


class CategoriesConfig(AppConfig):
    name = "categories"

    def ready(self):
        from . import signals  # noqa: F401
