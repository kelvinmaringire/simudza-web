from wagtail import hooks

from . import signals  # noqa: F401
from .viewsets import InventoryViewSet


@hooks.register("register_admin_viewset")
def register_inventory_viewset():
    return InventoryViewSet()
