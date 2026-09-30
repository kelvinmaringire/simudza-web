from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from businesses.models import Business
from categories.models import Category
from products.forms import unique_product_slug
from simudza.import_export_mixins import ImportUserMixin, VerificationLevelMixin

from .models import Product


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
            "sku",
            "barcode",
            "size_value",
            "size_unit",
            "price",
            "status",
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
        if should_set_slug:
            instance.slug = unique_product_slug(name, exclude_pk=instance.pk)
