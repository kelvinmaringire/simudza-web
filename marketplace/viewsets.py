from django.utils.translation import gettext_lazy as _

from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel, ObjectList
from wagtail.admin.viewsets.model import ModelViewSet, ModelViewSetGroup

from simudza.utils.admin_bulk_edit import BulkEditField, BulkEditViewSetMixin
from simudza.utils.admin_import_export import ImportExportViewSetMixin

from marketplace.cart_lifecycle import CART_STATUS_LABELS

from .forms import CartForm, CheckoutForm, OrderForm
from .models import Cart, Checkout, Order
from .resources import CartResource, CheckoutResource, OrderResource


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
    items = (CartViewSet(), OrderViewSet(), CheckoutViewSet())
