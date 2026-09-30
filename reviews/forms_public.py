from django import forms

from .models import (
    BUSINESS_REPORT_REASONS,
    PRODUCT_REPORT_REASONS,
    ReportReason,
)


class ListingReportForm(forms.Form):
    reason = forms.ChoiceField(
        choices=(),
        widget=forms.RadioSelect,
        label="What seems outdated?",
    )
    details = forms.CharField(
        required=False,
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Optional details for our team…",
            }
        ),
        label="Additional details",
    )
    guest_name = forms.CharField(
        required=False,
        max_length=120,
        label="Your name",
    )
    guest_email = forms.EmailField(
        required=False,
        label="Your email",
    )
    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    def __init__(self, *args, kind="product", **kwargs):
        self.kind = kind
        super().__init__(*args, **kwargs)
        if kind == "business":
            self.fields["reason"].choices = BUSINESS_REPORT_REASONS
            self._allowed_reasons = {value for value, _ in BUSINESS_REPORT_REASONS}
        else:
            self.fields["reason"].choices = PRODUCT_REPORT_REASONS
            self._allowed_reasons = {value for value, _ in PRODUCT_REPORT_REASONS}

    def clean_reason(self):
        reason = self.cleaned_data.get("reason")
        if reason not in self._allowed_reasons:
            raise forms.ValidationError("Please choose a valid reason for this listing.")
        return reason

    def is_honeypot_triggered(self):
        return bool((self.data.get("website") or "").strip())
