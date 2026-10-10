from django import forms

from history.context import change_context
from simudza.utils.slugs import save_with_unique_slug, unique_slug
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.forms.models import formfield_for_dbfield

from businesses.verification.levels import LifecycleStatus, VerificationLevel

from .models import Product, ProductVariant


def unique_product_slug(name, *, exclude_pk=None):
    """Build a unique slug from name, appending -2, -3, ... on collision."""
    return unique_slug(Product, name, fallback="product", exclude_pk=exclude_pk)


def save_product_with_unique_slug(product, *, name=None, save=None):
    return save_with_unique_slug(
        product, name or product.name, fallback="product", save=save
    )


class ProductForm(WagtailAdminModelForm):
    change_reason = forms.CharField(
        required=False,
        max_length=500,
        label="Reason for change",
        help_text="Optional note stored in change history.",
    )

    class Meta:
        model = Product
        # Required so Wagtail widget overrides (image chooser, etc.)
        # are applied. Defining Meta without this drops the parent callback.
        formfield_callback = formfield_for_dbfield
        fields = [
            "business",
            "name",
            "short_description",
            "description",
            "category",
            "origin_type",
            "brand_name",
            "status",
            "featured",
            "image",
            "verified_at",
            "verification_level",
            "verification_reference",
            "lifecycle_status",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "verification_level" in self.fields:
            self.fields["verification_level"].required = False
            if not self.initial.get("verification_level") and not (
                self.instance and self.instance.verification_level
            ):
                self.initial["verification_level"] = VerificationLevel.UNVERIFIED
        if "lifecycle_status" in self.fields:
            self.fields["lifecycle_status"].required = False

    def clean_verification_level(self):
        from businesses.verification.workflow import level_change_error

        level = self.cleaned_data.get("verification_level")
        old_level = self.instance.verification_level if self.instance.pk else None
        error = level and level_change_error(self.for_user, old_level, level)
        if error:
            raise forms.ValidationError(error)
        return level

    def clean_lifecycle_status(self):
        return (
            self.cleaned_data.get("lifecycle_status")
            or self.instance.lifecycle_status
            or LifecycleStatus.ACTIVE
        )

    def save(self, commit=True):
        # Slug is set once (and may refresh while draft). Once the product has
        # left draft, keep the existing slug so directory URLs stay stable.
        name = self.cleaned_data.get("name") or self.instance.name or "product"
        should_set_slug = not self.instance.slug

        if self.instance.pk and self.instance.slug:
            previous_status = (
                Product.objects.filter(pk=self.instance.pk)
                .values_list("status", flat=True)
                .first()
            )
            should_set_slug = previous_status == Product.ProductStatus.DRAFT

        if should_set_slug:
            self.instance.slug = unique_product_slug(
                name,
                exclude_pk=self.instance.pk,
            )

        product = super().save(commit=False)
        if not product.verification_level:
            product.verification_level = VerificationLevel.UNVERIFIED
        reason = (self.cleaned_data.get("change_reason") or "").strip()
        with change_context(reason=reason):
            if commit:
                if should_set_slug:
                    save_product_with_unique_slug(product, name=name)
                else:
                    product.save()
                self.save_m2m()
        return product


class ProductVariantForm(WagtailAdminModelForm):
    change_reason = forms.CharField(
        required=False,
        max_length=500,
        label="Reason for change",
        help_text="Optional note stored in change history.",
    )

    class Meta:
        model = ProductVariant
        formfield_callback = formfield_for_dbfield
        fields = [
            "product",
            "name",
            "sku",
            "barcode",
            "size_value",
            "size_unit",
            "packaging",
            "price",
            "is_available",
        ]

    def save(self, commit=True):
        variant = super().save(commit=False)
        reason = (self.cleaned_data.get("change_reason") or "").strip()
        with change_context(reason=reason):
            if commit:
                variant.save()
                self.save_m2m()
        return variant
