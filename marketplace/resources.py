from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from accounts.models import CustomUser
from .models import Cart, Checkout, Order
from products.models import Product


def _format_order_items(order):
    parts = []
    for item in order.items.all():
        parts.append(f"{item.product_name} x{item.quantity} @ {item.unit_price}")
    return "; ".join(parts)


def _format_cart_items(cart):
    parts = []
    for item in cart.items.all():
        parts.append(f"{item.product.name} x{item.quantity}")
    return "; ".join(parts)


class CartResource(resources.ModelResource):
    user = fields.Field(
        column_name="user",
        attribute="user",
        widget=ForeignKeyWidget(CustomUser, "username"),
    )
    items = fields.Field(column_name="items", readonly=True)

    class Meta:
        model = Cart
        import_id_fields = ("id",)
        skip_unchanged = True
        fields = ("id", "user", "items")
        export_order = fields

    def dehydrate_items(self, cart):
        return _format_cart_items(cart)


class OrderResource(resources.ModelResource):
    user = fields.Field(
        column_name="user",
        attribute="user",
        widget=ForeignKeyWidget(CustomUser, "username"),
    )
    items = fields.Field(column_name="items", readonly=True)

    class Meta:
        model = Order
        import_id_fields = ("id",)
        skip_unchanged = True
        fields = (
            "id",
            "user",
            "status",
            "subtotal",
            "delivery_fee",
            "total",
            "items",
        )
        export_order = fields

    def dehydrate_items(self, order):
        return _format_order_items(order)


class CheckoutResource(resources.ModelResource):
    user = fields.Field(
        column_name="user",
        attribute="user",
        widget=ForeignKeyWidget(CustomUser, "username"),
    )
    cart = fields.Field(
        column_name="cart",
        attribute="cart",
        widget=ForeignKeyWidget(Cart, "id"),
    )
    order = fields.Field(
        column_name="order",
        attribute="order",
        widget=ForeignKeyWidget(Order, "id"),
    )

    class Meta:
        model = Checkout
        import_id_fields = ("id",)
        skip_unchanged = True
        fields = (
            "id",
            "user",
            "cart",
            "order",
            "delivery_fee",
            "status",
        )
        export_order = fields
