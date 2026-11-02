from django.urls import path

from marketplace.checkout.checkout_views import (
    CheckoutEntryView,
    CheckoutPaymentCallbackView,
    CheckoutStepView,
    OrderConfirmationView,
    PaystackWebhookView,
)
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
    path("checkout/", CheckoutEntryView.as_view(), name="checkout"),
    path("checkout/<slug:step>/", CheckoutStepView.as_view(), name="checkout_step"),
    path(
        "checkout/payment/callback/",
        CheckoutPaymentCallbackView.as_view(),
        name="checkout_payment_callback",
    ),
    path(
        "checkout/paystack/webhook/",
        PaystackWebhookView.as_view(),
        name="checkout_paystack_webhook",
    ),
    path(
        "orders/<int:order_id>/confirmation/",
        OrderConfirmationView.as_view(),
        name="order_confirmation",
    ),
]
