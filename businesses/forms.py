from django import forms
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.forms.models import formfield_for_dbfield

from categories.models import Category
from products.models import Product

from .models import Business, save_business_with_unique_slug, unique_business_slug
from .services import owner_save_company, owner_save_product
from .verification.levels import LifecycleStatus


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
    owner_confirmed = forms.BooleanField(
        required=False,
        label="Ownership confirmed",
        help_text=(
            "Tick once Simudza has confirmed the owner represents this business. "
            "Confirmed owners' edits count as Information source checked."
        ),
    )

    change_reason = forms.CharField(
        required=False,
        max_length=500,
        label="Reason for change",
        help_text="Optional note stored in change history.",
    )

    class Meta:
        model = Business
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
            "verification_level",
            "verification_reference",
            "verified_at",
            "owner",
            "is_active",
            "lifecycle_status",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["owner_confirmed"].initial = self.instance.owner_is_confirmed
        else:
            self.fields["owner_confirmed"].initial = True
        user = self.for_user
        if (
            "owner" in self.fields
            and not self.instance.owner_id
            and user is not None
            and user.is_authenticated
        ):
            self.initial.setdefault("owner", user.pk)
        if "lifecycle_status" in self.fields:
            self.fields["lifecycle_status"].required = False

    def clean_lifecycle_status(self):
        return (
            self.cleaned_data.get("lifecycle_status")
            or self.instance.lifecycle_status
            or LifecycleStatus.ACTIVE
        )

    def clean_verification_level(self):
        from .verification.workflow import level_change_error

        level = self.cleaned_data.get("verification_level")
        old_level = self.instance.verification_level if self.instance.pk else None
        error = level and level_change_error(self.for_user, old_level, level)
        if error:
            raise forms.ValidationError(error)
        return level

    def save(self, commit=True):
        from .verification.workflow import set_ownership_confirmed

        business = super().save(commit=False)

        business.slug = unique_business_slug(
            business.name,
            exclude_pk=business.pk,
        )

        user = self.for_user
        if (
            not business.owner_id
            and user
            and user.is_authenticated
        ):
            business.owner = user

        set_ownership_confirmed(
            business,
            bool(self.cleaned_data.get("owner_confirmed") and business.owner_id),
        )

        from history.context import change_context

        reason = (self.cleaned_data.get("change_reason") or "").strip()
        with change_context(reason=reason):
            if commit:
                save_business_with_unique_slug(business)

        return business


class OwnerCompanyForm(forms.ModelForm):
    logo_upload = forms.ImageField(required=False)

    class Meta:
        model = Business
        fields = [
            "name",
            "business_type",
            "description",
            "website",
            "email",
            "phone",
            "address",
            "town_or_city",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "address": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, business=None, **kwargs):
        self.user = user
        self.editing_business = business
        instance = business if business is not None else Business()
        super().__init__(*args, instance=instance, **kwargs)
        _style_fields(self)
        self.fields["name"].required = True
        self.fields["business_type"].required = True
        self.fields["business_type"].choices = [
            ("", "Select type"),
            *Business.BusinessType.choices,
        ]

    def save(self, commit=True):
        if not commit:
            raise ValueError("OwnerCompanyForm always commits via owner_save_company.")
        return owner_save_company(
            self.user,
            self.cleaned_data,
            business=self.editing_business,
            logo_upload=self.cleaned_data.get("logo_upload"),
        )


class OwnerProductForm(forms.Form):
    business = forms.ModelChoiceField(
        queryset=Business.objects.none(),
        required=True,
    )
    name = forms.CharField(max_length=250, label="Product name")
    short_description = forms.CharField(max_length=300, required=False)
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), required=False)
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True).order_by("name"),
        required=True,
    )
    origin_type = forms.ChoiceField(choices=Product.OriginType.choices, required=True)
    brand_name = forms.CharField(max_length=200, required=False)
    sku = forms.CharField(max_length=100, required=False)
    barcode = forms.CharField(max_length=100, required=False)
    size_value = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    size_unit = forms.CharField(max_length=30, required=False)
    price = forms.DecimalField(max_digits=10, decimal_places=2, required=False)
    image_upload = forms.ImageField(required=False, label="Product image")

    def __init__(self, *args, user=None, product=None, **kwargs):
        self.user = user
        self.existing_product = product
        super().__init__(*args, **kwargs)
        _style_fields(self)
        owned = Business.objects.filter(owner=user).order_by("name")
        self.fields["business"].queryset = owned
        self.fields["origin_type"].choices = [
            ("", "Select product type"),
            *Product.OriginType.choices,
        ]
        if product is not None:
            self.fields["business"].initial = product.business_id
            self.fields["name"].initial = product.name
            self.fields["short_description"].initial = product.short_description
            self.fields["description"].initial = product.description
            self.fields["category"].initial = product.category_id
            self.fields["origin_type"].initial = product.origin_type
            self.fields["brand_name"].initial = product.brand_name
            variant = product.variants.order_by("sort_order", "pk").first()
            if variant:
                self.fields["sku"].initial = variant.sku
                self.fields["barcode"].initial = variant.barcode
                self.fields["size_value"].initial = variant.size_value
                self.fields["size_unit"].initial = variant.size_unit
                self.fields["price"].initial = variant.price
            self.fields["business"].widget = forms.HiddenInput()
            _style_fields(self)

    def clean(self):
        cleaned = super().clean()
        business = cleaned.get("business")
        product = self.existing_product
        if business and business.owner_id != self.user.id:
            self.add_error("business", "You can only submit for companies you own.")
        if product and product.business.owner_id != self.user.id:
            raise forms.ValidationError("You can only update products you own.")
        if product and business and product.business_id != business.id:
            self.add_error(
                "business",
                "That product does not belong to the selected company.",
            )
        return cleaned

    def save(self):
        business = self.cleaned_data["business"]
        data = {
            "name": self.cleaned_data["name"],
            "short_description": self.cleaned_data.get("short_description"),
            "description": self.cleaned_data.get("description"),
            "category": self.cleaned_data["category"],
            "origin_type": self.cleaned_data["origin_type"],
            "brand_name": self.cleaned_data.get("brand_name"),
            "sku": self.cleaned_data.get("sku"),
            "barcode": self.cleaned_data.get("barcode"),
            "size_value": self.cleaned_data.get("size_value"),
            "size_unit": self.cleaned_data.get("size_unit"),
            "price": self.cleaned_data.get("price"),
        }
        return owner_save_product(
            self.user,
            business,
            data,
            product=self.existing_product,
            image_upload=self.cleaned_data.get("image_upload"),
        )
