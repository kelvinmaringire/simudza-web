from django.utils.text import slugify
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.forms.models import formfield_for_dbfield

from .models import Product


def unique_product_slug(name, *, exclude_pk=None):
    """Build a unique slug from name, appending -2, -3, ... on collision."""
    base = slugify(name) or "product"
    candidate = base
    suffix = 2
    queryset = Product.objects.all()
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    while queryset.filter(slug=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


class ProductForm(WagtailAdminModelForm):
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
            "country_of_origin",
            "brand_name",
            "sku",
            "barcode",
            "size_value",
            "size_unit",
            "price",
            "status",
            "featured",
            "image",
            "verified_at",
        ]

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

        return super().save(commit=commit)
