from wagtail import hooks

from . import signals  # noqa: F401
from .viewsets import InventoryViewSet


@hooks.register("register_admin_viewset")
def register_inventory_viewset():
    return InventoryViewSet()


hooks.register("register_bulk_action", InventoryViewSet.bulk_edit_action)
