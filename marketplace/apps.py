from django.apps import AppConfig


class MarketplaceConfig(AppConfig):
    name = "marketplace"

    def ready(self):
        from . import signals  # noqa: F401
