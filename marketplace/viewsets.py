from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel, ObjectList
from wagtail.admin.viewsets.model import ModelViewSet, ModelViewSetGroup

from .forms import CartForm, CheckoutForm, OrderForm
from .models import Cart, Checkout, Order


class CartViewSet(ModelViewSet):
    model = Cart

    name = "cart"
    menu_label = "Carts"
    menu_icon = "shopping-cart"
    add_to_admin_menu = False

    list_display = [
        "user",
        "item_count",
        "updated_at",
    ]

    search_fields = [
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
    ]

    edit_handler = ObjectList(
        [
            MultiFieldPanel(
                [
                    FieldPanel("user"),
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
        "item_count",
        "created_at",
        "updated_at",
    ]


class OrderViewSet(ModelViewSet):
    model = Order

    name = "order"
    menu_label = "Orders"
    menu_icon = "order"
    add_to_admin_menu = False

    list_display = [
        "id",
        "user",
        "status",
        "total",
        "created_at",
    ]

    list_filter = [
        "status",
    ]

    search_fields = [
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "items__product_name",
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


class CheckoutViewSet(ModelViewSet):
    model = Checkout

    name = "checkout"
    menu_label = "Checkouts"
    menu_icon = "clipboard-list"
    add_to_admin_menu = False

    list_display = [
        "id",
        "user",
        "cart",
        "status",
        "order",
        "created_at",
    ]

    list_filter = [
        "status",
    ]

    search_fields = [
        "user__username",
        "user__email",
    ]

    edit_handler = ObjectList(
        [
            MultiFieldPanel(
                [
                    FieldPanel("user"),
                    FieldPanel("cart"),
                    FieldPanel("delivery_fee"),
                    FieldPanel("status"),
                    FieldPanel("order", read_only=True),
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
    menu_icon = "desktop"
    items = (
        CartViewSet,
        OrderViewSet,
        CheckoutViewSet,
    )
