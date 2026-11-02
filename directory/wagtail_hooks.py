from wagtail import hooks

from .viewsets import DirectoryListingViewSet

hooks.register("register_bulk_action", DirectoryListingViewSet.bulk_edit_action)
