from wagtail import hooks

from . import signals  # noqa: F401
from .viewsets import DirectoryListingViewSet


@hooks.register("register_admin_viewset")
def register_directory_listing_viewset():
    return DirectoryListingViewSet()
