from django.urls import path

from .views import (
    MarketplaceIndexView,
    MarketplaceProductDetailView,
    MarketplaceResultsView,
    cart_sync,
)

app_name = "marketplace"

urlpatterns = [
    path("", MarketplaceIndexView.as_view(), name="index"),
    path("results/", MarketplaceResultsView.as_view(), name="results"),
    path("cart/sync/", cart_sync, name="cart_sync"),
    path(
        "products/<slug:slug>/",
        MarketplaceProductDetailView.as_view(),
        name="product_detail",
    ),
]
