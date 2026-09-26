from django import forms
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.forms.models import formfield_for_dbfield

from categories.models import Category
from products.models import Product

from .models import Business, ManufacturerSubmission, unique_business_slug
from .services import apply_submission


INPUT_CLASS = "input input-bordered w-full"
SELECT_CLASS = "select select-bordered w-full"
TEXTAREA_CLASS = "textarea textarea-bordered w-full"
FILE_CLASS = "file-input file-input-bordered w-full"


def _style_fields(form):
    for name, field in form.fields.items():
        widget = field.widget
        if isinstance(widget, forms.FileInput):
            widget.attrs.setdefault("class", FILE_CLASS)
        elif isinstance(widget, forms.Select):
            widget.attrs.setdefault("class", SELECT_CLASS)
        elif isinstance(widget, forms.Textarea):
            widget.attrs.setdefault("class", TEXTAREA_CLASS)
        elif isinstance(widget, forms.NumberInput):
            widget.attrs.setdefault("class", INPUT_CLASS)
        elif isinstance(widget, (forms.TextInput, forms.URLInput, forms.EmailInput)):
            widget.attrs.setdefault("class", INPUT_CLASS)
        else:
            widget.attrs.setdefault("class", INPUT_CLASS)


class BusinessForm(WagtailAdminModelForm):
    class Meta:
        model = Business
        # Required so Wagtail widget overrides (image chooser, date picker)
        # are applied. Defining Meta without this drops the parent callback.
        formfield_callback = formfield_for_dbfield
        fields = [
            "name",
            "business_type",
            "description",
            "logo",
            "website",
            "email",
            "phone",
            "address",
            "town_or_city",
            "verification_status",
            "verified_at",
            "is_active",
        ]

    def save(self, commit=True):
        business = super().save(commit=False)

        business.slug = unique_business_slug(
            business.name,
            exclude_pk=business.pk,
        )

        # ModelViewSet passes the request user as for_user.
        user = self.for_user
        if (
            not business.owner_id
            and user
            and user.is_authenticated
        ):
            business.owner = user

        if commit:
            business.save()

        return business


class CompanySubmissionForm(forms.ModelForm):
    class Meta:
        model = ManufacturerSubmission
        fields = [
            "business",
            "company_name",
            "business_type",
            "company_description",
            "website",
            "email",
            "phone",
            "address",
            "town_or_city",
            "logo_upload",
            "submitter_notes",
        ]
        widgets = {
            "company_description": forms.Textarea(attrs={"rows": 4}),
            "address": forms.Textarea(attrs={"rows": 3}),
            "submitter_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        _style_fields(self)
        owned = Business.objects.filter(owner=user).order_by("name")
        self.fields["business"].queryset = owned
        self.fields["business"].required = False
        self.fields["business"].empty_label = "Register a new company"
        self.fields["business"].help_text = (
            "Leave blank to register a new company profile."
            if not owned.exists()
            else "Choose a company you own, or leave blank to add another."
        )
        self.fields["company_name"].required = True
        self.fields["business_type"].required = True
        self.fields["business_type"].choices = [
            ("", "Select type"),
            *Business.BusinessType.choices,
        ]

    def clean(self):
        cleaned = super().clean()
        business = cleaned.get("business")
        if business and business.owner_id != self.user.id:
            self.add_error("business", "You can only update companies you own.")
        return cleaned

    def save(self, commit=True):
        submission = super().save(commit=False)
        submission.kind = ManufacturerSubmission.Kind.COMPANY_PROFILE
        submission.submitted_by = self.user
        submission.status = ManufacturerSubmission.Status.PENDING
        if commit:
            submission.save()
            if submission.can_auto_apply(self.user):
                apply_submission(submission)
        return submission


class ProductSubmissionForm(forms.ModelForm):
    class Meta:
        model = ManufacturerSubmission
        fields = [
            "business",
            "product",
            "product_name",
            "short_description",
            "product_description",
            "category",
            "origin_type",
            "brand_name",
            "sku",
            "barcode",
            "size_value",
            "size_unit",
            "price",
            "product_image_upload",
            "submitter_notes",
        ]
        widgets = {
            "product_description": forms.Textarea(attrs={"rows": 4}),
            "submitter_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, product=None, **kwargs):
        self.user = user
        self.existing_product = product
        super().__init__(*args, **kwargs)
        _style_fields(self)
        owned = Business.objects.filter(owner=user, is_active=True).order_by("name")
        self.fields["business"].queryset = owned
        self.fields["business"].required = True
        self.fields["category"].queryset = Category.objects.filter(
            is_active=True,
        ).order_by("name")
        self.fields["category"].required = True
        self.fields["product_name"].required = True
        self.fields["origin_type"].choices = [
            ("", "Select product type"),
            *Product.OriginType.choices,
        ]
        self.fields["origin_type"].required = True
        self.fields["product"].queryset = Product.objects.filter(
            business__owner=user,
        ).order_by("name")
        self.fields["product"].required = False
        self.fields["product"].empty_label = "Create a new product"
        if product is not None:
            self.fields["product"].initial = product
            self.fields["business"].initial = product.business
            self.fields["product_name"].initial = product.name
            self.fields["short_description"].initial = product.short_description
            self.fields["product_description"].initial = product.description
            self.fields["category"].initial = product.category_id
            self.fields["origin_type"].initial = product.origin_type
            self.fields["brand_name"].initial = product.brand_name
            self.fields["sku"].initial = product.sku
            self.fields["barcode"].initial = product.barcode
            self.fields["size_value"].initial = product.size_value
            self.fields["size_unit"].initial = product.size_unit
            self.fields["price"].initial = product.price
            self.fields["product"].widget = forms.HiddenInput()
            self.fields["business"].widget = forms.HiddenInput()
            _style_fields(self)
    def clean(self):
        cleaned = super().clean()
        business = cleaned.get("business")
        product = cleaned.get("product") or self.existing_product
        if business and business.owner_id != self.user.id:
            self.add_error("business", "You can only submit for companies you own.")
        if product and product.business.owner_id != self.user.id:
            self.add_error("product", "You can only update products you own.")
        if product and business and product.business_id != business.id:
            self.add_error(
                "product",
                "That product does not belong to the selected company.",
            )
        return cleaned

    def save(self, commit=True):
        submission = super().save(commit=False)
        product = self.cleaned_data.get("product") or self.existing_product
        submission.product = product
        submission.kind = (
            ManufacturerSubmission.Kind.PRODUCT_UPDATE
            if product
            else ManufacturerSubmission.Kind.NEW_PRODUCT
        )
        submission.submitted_by = self.user
        submission.status = ManufacturerSubmission.Status.PENDING
        if commit:
            submission.save()
            if submission.can_auto_apply(self.user):
                apply_submission(submission)
        return submission


class RetailLocationSubmissionForm(forms.ModelForm):
    class Meta:
        model = ManufacturerSubmission
        fields = [
            "business",
            "location_name",
            "location_address",
            "location_town_or_city",
            "location_phone",
            "location_notes",
            "submitter_notes",
        ]
        widgets = {
            "location_address": forms.Textarea(attrs={"rows": 3}),
            "location_notes": forms.Textarea(attrs={"rows": 3}),
            "submitter_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        _style_fields(self)
        owned = Business.objects.filter(owner=user, is_active=True).order_by("name")
        self.fields["business"].queryset = owned
        self.fields["business"].required = True
        self.fields["location_name"].required = True

    def clean(self):
        cleaned = super().clean()
        business = cleaned.get("business")
        if business and business.owner_id != self.user.id:
            self.add_error("business", "You can only add locations for companies you own.")
        return cleaned

    def save(self, commit=True):
        submission = super().save(commit=False)
        submission.kind = ManufacturerSubmission.Kind.RETAIL_LOCATION
        submission.submitted_by = self.user
        submission.status = ManufacturerSubmission.Status.PENDING
        if commit:
            submission.save()
            if submission.can_auto_apply(self.user):
                apply_submission(submission)
        return submission
