from wagtail import hooks

from .viewsets import MarketplaceViewSetGroup


@hooks.register("register_admin_viewset")
def register_marketplace_viewset_group():
    return MarketplaceViewSetGroup()
