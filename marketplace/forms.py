from django import forms
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.forms.models import formfield_for_dbfield

from history.context import change_context
from marketplace.settings import CompactTaxRateInput
from marketplace.tax import format_tax_rate

from .models import Cart, Checkout, Order, VariantOffer


def _prefer_short_tax_rate(form):
    rate = form.initial.get("tax_rate")
    if rate in (None, "") and getattr(form.instance, "pk", None):
        rate = getattr(form.instance, "tax_rate", None)
    if rate not in (None, ""):
        form.initial["tax_rate"] = format_tax_rate(rate)
    if "tax_rate" in form.fields:
        form.fields["tax_rate"].widget = CompactTaxRateInput()


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
            "stock_mode",
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
            "tax_enabled",
            "tax_pricing_mode",
            "tax_rate",
            "tax_amount",
            "currency",
            "total",
            "customer_name",
            "customer_email",
            "customer_phone",
            "fulfilment_method",
            "payment_status",
            "payment_reference",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _prefer_short_tax_rate(self)


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
            "customer_name",
            "customer_email",
            "customer_phone",
            "fulfilment_method",
            "payment_status",
            "payment_reference",
            "tax_enabled",
            "tax_pricing_mode",
            "tax_rate",
            "tax_amount",
            "total_payable",
            "currency",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _prefer_short_tax_rate(self)
