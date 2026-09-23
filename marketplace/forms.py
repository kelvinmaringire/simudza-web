from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.forms.models import formfield_for_dbfield

from .models import Cart, Checkout, Order


class CartForm(WagtailAdminModelForm):
    class Meta:
        model = Cart
        formfield_callback = formfield_for_dbfield
        fields = ["user"]


class OrderForm(WagtailAdminModelForm):
    class Meta:
        model = Order
        formfield_callback = formfield_for_dbfield
        fields = [
            "user",
            "status",
            "subtotal",
            "delivery_fee",
            "total",
        ]


class CheckoutForm(WagtailAdminModelForm):
    class Meta:
        model = Checkout
        formfield_callback = formfield_for_dbfield
        fields = [
            "user",
            "cart",
            "delivery_fee",
            "status",
            "order",
        ]
