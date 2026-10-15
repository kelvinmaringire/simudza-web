from django import forms
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.forms.models import formfield_for_dbfield

from history.context import change_context

from .models import Cart, Checkout, Order, VariantOffer


class VariantOfferForm(WagtailAdminModelForm):
    change_reason = forms.CharField(
        required=False,
        max_length=500,
        label="Reason for change",
        help_text="Optional note stored in change history.",
    )

    class Meta:
        model = VariantOffer
        formfield_callback = formfield_for_dbfield
        fields = [
            "price",
            "is_available",
        ]

    def save(self, commit=True):
        offer = super().save(commit=False)
        reason = (self.cleaned_data.get("change_reason") or "").strip()
        with change_context(reason=reason):
            if commit:
                offer.save()
                self.save_m2m()
        return offer


class CartForm(WagtailAdminModelForm):
    class Meta:
        model = Cart
        formfield_callback = formfield_for_dbfield
        fields = [
            "user",
            "last_activity_at",
            "converted_at",
            "merged_into",
        ]


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
