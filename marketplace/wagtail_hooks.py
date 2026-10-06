from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem

from .admin_views import CartAnalyticsIndexView
from .cart_analytics import user_can_view_cart_analytics
from .viewsets import CheckoutViewSet, MarketplaceViewSetGroup, OrderViewSet


@hooks.register("register_admin_viewset")
def register_marketplace_viewset_group():
    return MarketplaceViewSetGroup()


hooks.register("register_bulk_action", OrderViewSet.bulk_edit_action)
hooks.register("register_bulk_action", CheckoutViewSet.bulk_edit_action)


@hooks.register("register_admin_urls")
def register_cart_analytics_urls():
    return [
        path(
            "cart-analytics/",
            CartAnalyticsIndexView.as_view(),
            name="simudza_cart_analytics_index",
        ),
    ]


@hooks.register("register_admin_menu_item")
def register_cart_analytics_menu_item():
    class CartAnalyticsMenuItem(MenuItem):
        def is_shown(self, request):
            return user_can_view_cart_analytics(request.user)

    return CartAnalyticsMenuItem(
        "Cart analytics",
        reverse("simudza_cart_analytics_index"),
        name="cart-analytics",
        icon_name="shopping-cart",
        order=196,
    )
