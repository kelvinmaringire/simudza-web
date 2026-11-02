from django import forms

from marketplace.models import FulfilmentMethod


class CustomerCheckoutForm(forms.Form):
    customer_name = forms.CharField(
        max_length=200,
        label="Full name",
        widget=forms.TextInput(attrs={"class": "input input-bordered w-full", "autocomplete": "name"}),
    )
    customer_email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={"class": "input input-bordered w-full", "autocomplete": "email"}
        ),
    )
    customer_phone = forms.CharField(
        max_length=32,
        label="Phone",
        widget=forms.TextInput(
            attrs={"class": "input input-bordered w-full", "autocomplete": "tel"}
        ),
    )


class FulfilmentCheckoutForm(forms.Form):
    fulfilment_method = forms.ChoiceField(
        choices=FulfilmentMethod.choices,
        label="How would you like to receive your order?",
        widget=forms.RadioSelect,
    )
    delivery_city = forms.CharField(
        max_length=120,
        required=False,
        label="City",
        widget=forms.TextInput(attrs={"class": "input input-bordered w-full"}),
    )
    delivery_suburb = forms.CharField(
        max_length=120,
        required=False,
        label="Suburb",
        widget=forms.TextInput(attrs={"class": "input input-bordered w-full"}),
    )
    delivery_street = forms.CharField(
        max_length=250,
        required=False,
        label="Street address",
        widget=forms.TextInput(attrs={"class": "input input-bordered w-full"}),
    )
    delivery_instructions = forms.CharField(
        required=False,
        label="Delivery instructions",
        widget=forms.Textarea(
            attrs={"class": "textarea textarea-bordered w-full", "rows": 3}
        ),
    )

    def __init__(self, *args, collection_enabled=True, **kwargs):
        super().__init__(*args, **kwargs)
        if collection_enabled:
            self.fields["fulfilment_method"].choices = list(FulfilmentMethod.choices)
        else:
            self.fields["fulfilment_method"].choices = [
                (value, label)
                for value, label in FulfilmentMethod.choices
                if value != FulfilmentMethod.COLLECTION
            ]


class PaymentCheckoutForm(forms.Form):
    payment_method = forms.ChoiceField(
        choices=[("paystack", "Pay with Paystack (card, bank, mobile money)")],
        initial="paystack",
        widget=forms.RadioSelect,
    )


class ReviewCheckoutForm(forms.Form):
    accept_terms = forms.BooleanField(
        required=True,
        label="I agree to the marketplace terms and understand my order is subject to seller fulfilment.",
    )
