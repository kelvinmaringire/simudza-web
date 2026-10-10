from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from businesses.models import Business
from categories.models import Category
from products.forms import save_product_with_unique_slug
from simudza.utils.import_export_mixins import ImportUserMixin, VerificationLevelMixin

from .models import Product, ProductVariant


class ProductResource(ImportUserMixin, VerificationLevelMixin, resources.ModelResource):
    business = fields.Field(
        column_name="business",
        attribute="business",
        widget=ForeignKeyWidget(Business, "slug"),
    )
    category = fields.Field(
        column_name="category",
        attribute="category",
        widget=ForeignKeyWidget(Category, "slug"),
    )

    class Meta:
        model = Product
        import_id_fields = ("slug",)
        skip_unchanged = True
        fields = (
            "slug",
            "name",
            "business",
            "category",
            "short_description",
            "description",
            "origin_type",
            "brand_name",
            "status",
            "lifecycle_status",
            "featured",
            "verification_level",
            "verification_reference",
            "verified_at",
        )
        export_order = fields

    def before_save_instance(self, instance, row, **kwargs):
        super().before_save_instance(instance, row, **kwargs)
        name = instance.name or "product"
        should_set_slug = not instance.slug
        if instance.pk and instance.slug:
            previous_status = (
                Product.objects.filter(pk=instance.pk)
                .values_list("status", flat=True)
                .first()
            )
            should_set_slug = previous_status == Product.ProductStatus.DRAFT
        instance._generate_slug_from = name if should_set_slug else None

    def do_instance_save(self, instance, is_create):
        name = getattr(instance, "_generate_slug_from", None)
        if name:
            save_product_with_unique_slug(instance, name=name)
        else:
            instance.save()


class ProductVariantResource(resources.ModelResource):
    product = fields.Field(
        column_name="product",
        attribute="product",
        widget=ForeignKeyWidget(Product, "slug"),
    )

    class Meta:
        model = ProductVariant
        import_id_fields = ("product", "sku")
        skip_unchanged = True
        fields = (
            "product",
            "name",
            "sku",
            "barcode",
            "size_value",
            "size_unit",
            "packaging",
            "price",
            "is_available",
            "sort_order",
        )
        export_order = fields
