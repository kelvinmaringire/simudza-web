from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from products.models import Product

from .models import Inventory


class InventoryResource(resources.ModelResource):
    product = fields.Field(
        column_name="product",
        attribute="product",
        widget=ForeignKeyWidget(Product, "slug"),
    )

    class Meta:
        model = Inventory
        import_id_fields = ("product",)
        skip_unchanged = True
        fields = (
            "id",
            "product",
            "quantity",
            "reserved_quantity",
            "low_stock_threshold",
        )
        export_order = fields
