from django.urls import path
from django.utils.translation import gettext_lazy as _

from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel, ObjectList
from wagtail.admin.viewsets.model import ModelViewSet, ModelViewSetGroup

from history.panels import ChangeHistoryPanel
from inventory.viewsets import InventoryViewSet
from simudza.utils.admin_bulk_edit import BulkEditField, BulkEditViewSetMixin
from simudza.utils.admin_import_export import ImportExportViewSetMixin

from marketplace.cart_lifecycle import CART_STATUS_LABELS

from .forms import CartForm, CheckoutForm, OrderForm, VariantOfferForm
from .models import Cart, Checkout, Order, VariantOffer
from .resources import (
    CartResource,
    CheckoutResource,
    OrderResource,
    VariantOfferResource,
)


class VariantOfferViewSet(BulkEditViewSetMixin, ImportExportViewSetMixin, ModelViewSet):
    model = VariantOffer
    resource_class = VariantOfferResource

    bulk_edit_fields = [
        BulkEditField("price"),
        BulkEditField("is_available"),
    ]

    name = "variant_offer"
    menu_label = "Prices"
    menu_icon = "tag"
    add_to_admin_menu = False
    copy_view_enabled = False

    list_display = [
        "variant",
        "price",
        "is_available",
        "updated_at",
    ]

    list_filter = [
        "is_available",
        "variant__product__status",
        "variant__product__category",
        "variant__product__business",
    ]

    search_fields = [
        "variant__product__name",
        "variant__product__slug",
        "variant__inventory__sku",
        "variant__product__brand_name",
        "variant__product__business__name",
    ]

    # Offers are auto-created with each variant — edit selling terms only.
    edit_handler = ObjectList(
        [
            MultiFieldPanel(
                [
                    FieldPanel("variant", read_only=True),
                    FieldPanel("price"),
                    FieldPanel("is_available"),
                ],
                heading="Pricing & availability",
            ),
            FieldPanel("change_reason"),
            ChangeHistoryPanel(),
        ],
        base_form_class=VariantOfferForm,
    )

    inspect_view_enabled = True

    inspect_view_fields = [
        "variant",
        "price",
        "is_available",
        "created_at",
        "updated_at",
    ]

    def get_queryset(self, request):
        return VariantOffer.objects.select_related("variant", "variant__product")

    def get_common_view_kwargs(self, **kwargs):
        view_kwargs = super().get_common_view_kwargs(**kwargs)
        view_kwargs["add_url_name"] = None
        view_kwargs["delete_url_name"] = None
        return view_kwargs

    def get_urlpatterns(self):
        conv = self.pk_path_converter
        patterns = [
            path("", self.index_view, name="index"),
            path("results/", self.index_results_view, name="index_results"),
            path(f"edit/<{conv}:pk>/", self.edit_view, name="edit"),
            path(f"history/<{conv}:pk>/", self.history_view, name="history"),
            path(
                f"history-results/<{conv}:pk>/",
                self.history_results_view,
                name="history_results",
            ),
            path(f"usage/<{conv}:pk>/", self.usage_view, name="usage"),
            path(f"inspect/<{conv}:pk>/", self.inspect_view, name="inspect"),
        ]
        patterns.extend(self.import_export_urlpatterns())
        return patterns


def cart_user_display(cart):
    if cart.user_id:
        return cart.user.get_username()
    return _("Guest")


cart_user_display.short_description = _("User")


def cart_lifecycle_display(cart):
    return CART_STATUS_LABELS.get(cart.lifecycle_status, cart.lifecycle_status.value)


cart_lifecycle_display.short_description = _("Status")


def cart_value_display(cart):
    value = getattr(cart, "cart_value", None)
    if value is None:
        return "0.00"
    return value


cart_value_display.short_description = _("Value")


class CartViewSet(ImportExportViewSetMixin, ModelViewSet):
    model = Cart
    resource_class = CartResource

    name = "cart"
    menu_label = "Carts"
    menu_icon = "shopping-cart"
    add_to_admin_menu = False

    list_display = [
        cart_user_display,
        cart_lifecycle_display,
        "item_count",
        cart_value_display,
        "last_activity_at",
    ]

    search_fields = [
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "token",
    ]

    edit_handler = ObjectList(
        [
            MultiFieldPanel(
                [
                    FieldPanel("user"),
                    FieldPanel("last_activity_at"),
                    FieldPanel("converted_at"),
                    FieldPanel("merged_into"),
                ],
                heading="Cart",
            ),
            InlinePanel("items", label="Cart item"),
        ],
        base_form_class=CartForm,
    )

    inspect_view_enabled = True

    inspect_view_fields = [
        "user",
        "token",
        "item_count",
        "last_activity_at",
        "converted_at",
        "merged_into",
        "created_at",
        "updated_at",
    ]

    def get_queryset(self, request):
        return (
            Cart.objects.filter(merged_into__isnull=True)
            .with_lifecycle()
            .with_value()
        )


class OrderViewSet(BulkEditViewSetMixin, ImportExportViewSetMixin, ModelViewSet):
    model = Order
    resource_class = OrderResource

    name = "order"
    menu_label = "Orders"
    menu_icon = "order"
    add_to_admin_menu = False

    list_display = [
        "user",
        "status",
        "total",
        "created_at",
    ]

    search_fields = [
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
    ]

    bulk_edit_fields = [
        BulkEditField("status"),
    ]

    edit_handler = ObjectList(
        [
            MultiFieldPanel(
                [
                    FieldPanel("user"),
                    FieldPanel("status"),
                    FieldPanel("subtotal"),
                    FieldPanel("delivery_fee"),
                    FieldPanel("total"),
                ],
                heading="Order",
            ),
            InlinePanel("items", label="Order item"),
        ],
        base_form_class=OrderForm,
    )

    inspect_view_enabled = True

    inspect_view_fields = [
        "user",
        "status",
        "subtotal",
        "delivery_fee",
        "total",
        "created_at",
        "updated_at",
    ]


class CheckoutViewSet(BulkEditViewSetMixin, ImportExportViewSetMixin, ModelViewSet):
    model = Checkout
    resource_class = CheckoutResource

    name = "checkout"
    menu_label = "Checkouts"
    menu_icon = "doc-full"
    add_to_admin_menu = False

    list_display = [
        "user",
        "cart",
        "status",
        "order",
        "created_at",
    ]

    search_fields = [
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
    ]

    bulk_edit_fields = [
        BulkEditField("status"),
    ]

    edit_handler = ObjectList(
        [
            MultiFieldPanel(
                [
                    FieldPanel("user"),
                    FieldPanel("cart"),
                    FieldPanel("delivery_fee"),
                    FieldPanel("status"),
                    FieldPanel("order"),
                ],
                heading="Checkout",
            ),
        ],
        base_form_class=CheckoutForm,
    )

    inspect_view_enabled = True

    inspect_view_fields = [
        "user",
        "cart",
        "delivery_fee",
        "status",
        "order",
        "created_at",
        "updated_at",
    ]


class MarketplaceViewSetGroup(ModelViewSetGroup):
    menu_label = "Marketplace"
    menu_icon = "shopping-cart"
    menu_order = 630
    submenu_hook = "register_marketplace_menu_item"
    items = (
        VariantOfferViewSet(),
        InventoryViewSet(),
        CartViewSet(),
        OrderViewSet(),
        CheckoutViewSet(),
    )
