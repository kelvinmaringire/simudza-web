from django.core.exceptions import ValidationError
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.forms.models import formfield_for_dbfield

from .models import Inventory


class InventoryForm(WagtailAdminModelForm):
    class Meta:
        model = Inventory
        # Required so Wagtail widget overrides are applied.
        formfield_callback = formfield_for_dbfield
        fields = [
            "quantity",
            "reserved_quantity",
            "low_stock_threshold",
        ]

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get("quantity")
        reserved_quantity = cleaned_data.get("reserved_quantity")

        if (
            quantity is not None
            and reserved_quantity is not None
            and reserved_quantity > quantity
        ):
            raise ValidationError(
                {
                    "reserved_quantity": (
                        "Reserved quantity cannot exceed total quantity."
                    ),
                }
            )

        return cleaned_data
