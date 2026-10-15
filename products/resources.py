from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from businesses.models import Business
from categories.models import Category
from products.forms import save_product_with_unique_slug
from simudza.utils.import_export_mixins import ImportUserMixin, VerificationLevelMixin

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
    created_at = fields.Field(
        attribute="created_at", column_name="created_at", readonly=True
    )
    updated_at = fields.Field(
        attribute="updated_at", column_name="updated_at", readonly=True
    )
    # Recomputed from the listing on save, so imports cannot set them.
    quality_score = fields.Field(
        attribute="quality_score", column_name="quality_score", readonly=True
    )
    quality_issues = fields.Field(
        attribute="quality_issues", column_name="quality_issues", readonly=True
    )
    quality_checked_at = fields.Field(
        attribute="quality_checked_at",
        column_name="quality_checked_at",
        readonly=True,
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
            "quality_score",
            "quality_issues",
            "quality_checked_at",
            "created_at",
            "updated_at",
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
