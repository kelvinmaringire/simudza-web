from django.apps import AppConfig


class MarketplaceConfig(AppConfig):
    name = "marketplace"

    def ready(self):
        from . import signals  # noqa: F401
        from . import settings as marketplace_settings  # noqa: F401
