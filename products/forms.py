from django.utils.text import slugify
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.forms.models import formfield_for_dbfield

from .models import Product


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
        # Set slug before ClusterForm saves the product and related images.
        self.instance.slug = slugify(
            self.cleaned_data.get("name") or self.instance.name
        )
        return super().save(commit=commit)
