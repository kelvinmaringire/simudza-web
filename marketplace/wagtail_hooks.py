from wagtail import hooks

from .viewsets import CheckoutViewSet, MarketplaceViewSetGroup, OrderViewSet


@hooks.register("register_admin_viewset")
def register_marketplace_viewset_group():
    return MarketplaceViewSetGroup()


hooks.register("register_bulk_action", OrderViewSet.bulk_edit_action)
hooks.register("register_bulk_action", CheckoutViewSet.bulk_edit_action)
