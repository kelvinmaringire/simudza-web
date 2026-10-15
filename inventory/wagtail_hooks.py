from wagtail import hooks

from .viewsets import InventoryViewSet


hooks.register("register_bulk_action", InventoryViewSet.bulk_edit_action)
