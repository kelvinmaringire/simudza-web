from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from products.models import Product, ProductVariant

from .models import Inventory


class ProductVariantBySkuWidget(ForeignKeyWidget):
    """Resolve variant by product slug + variant SKU (SKU may be blank)."""

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
        return ProductVariant.objects.filter(product=product, sku=value).first()


class InventoryResource(resources.ModelResource):
    product = fields.Field(
        column_name="product",
        attribute="variant__product",
        widget=ForeignKeyWidget(Product, "slug"),
        readonly=True,
    )
    variant_sku = fields.Field(
        column_name="variant_sku",
        attribute="variant",
        widget=ProductVariantBySkuWidget(ProductVariant, "sku"),
    )

    class Meta:
        model = Inventory
        import_id_fields = ("variant",)
        skip_unchanged = True
        fields = (
            "id",
            "product",
            "variant_sku",
            "quantity",
            "reserved_quantity",
            "low_stock_threshold",
        )
        export_order = fields

    def dehydrate_variant_sku(self, inventory):
        sku = inventory.variant.sku
        return sku if sku else "-"
