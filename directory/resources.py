from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from products.models import Product

from .models import DirectoryListing


class DirectoryListingResource(resources.ModelResource):
    product = fields.Field(
        column_name="product",
        attribute="product",
        widget=ForeignKeyWidget(Product, "slug"),
    )

    class Meta:
        model = DirectoryListing
        import_id_fields = ("product",)
        skip_unchanged = True
        fields = (
            "id",
            "product",
            "featured",
            "show_in_directory",
            "views",
        )
        export_order = fields
