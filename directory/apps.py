from django.apps import AppConfig


class DirectoryConfig(AppConfig):
    name = "directory"

    def ready(self):
        from . import signals  # noqa: F401
