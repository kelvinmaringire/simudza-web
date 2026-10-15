from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from products.models import Product, ProductVariant

from .models import Inventory


class ProductVariantBySkuWidget(ForeignKeyWidget):
    """Resolve variant by product slug + inventory SKU ("-" = first variant)."""

    def __init__(self, **kwargs):
        super().__init__(ProductVariant, **kwargs)

    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        product_slug = (row or {}).get("product")
        if not product_slug:
            return None
        try:
            product = Product.objects.get(slug=product_slug)
        except Product.DoesNotExist:
            return None
        if value == "-":
            return product.variants.order_by("sort_order", "pk").first()
        return ProductVariant.objects.filter(
            product=product, inventory__sku=value
        ).first()

    def render(self, value, obj=None, **kwargs):
        if value is None:
            return ""
        inventory = getattr(value, "inventory", None)
        return (inventory.sku if inventory else "") or "-"


class InventoryResource(resources.ModelResource):
    product = fields.Field(
        column_name="product",
        attribute="variant__product",
        widget=ForeignKeyWidget(Product, "slug"),
        readonly=True,
    )
    variant = fields.Field(
        column_name="variant",
        attribute="variant",
        readonly=True,
    )

    class Meta:
        model = Inventory
        import_id_fields = ("id",)
        skip_unchanged = True
        fields = (
            "id",
            "product",
            "variant",
            "sku",
            "barcode",
            "quantity",
            "reserved_quantity",
            "low_stock_threshold",
        )
        export_order = fields

    def dehydrate_variant(self, inventory):
        return inventory.variant.label
