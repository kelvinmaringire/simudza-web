from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from accounts.models import CustomUser

from .models import Business, save_business_with_unique_slug
from simudza.utils.import_export_mixins import ImportUserMixin, VerificationLevelMixin


class BusinessResource(ImportUserMixin, VerificationLevelMixin, resources.ModelResource):
    # Database ids differ between environments; rows are matched on slug.
    id = fields.Field(attribute="id", column_name="id", readonly=True)
    owner = fields.Field(
        column_name="owner",
        attribute="owner",
        widget=ForeignKeyWidget(CustomUser, "username"),
    )
    created_at = fields.Field(
        attribute="created_at", column_name="created_at", readonly=True
    )
    updated_at = fields.Field(
        attribute="updated_at", column_name="updated_at", readonly=True
    )
    # Recomputed from the listing on save, so imports cannot set it.
    quality_score = fields.Field(
        attribute="quality_score", column_name="quality_score", readonly=True
    )

    class Meta:
        model = Business
        import_id_fields = ("slug",)
        skip_unchanged = True
        fields = (
            "id",
            "slug",
            "name",
            "business_type",
            "description",
            "website",
            "email",
            "phone",
            "address",
            "town_or_city",
            "verification_level",
            "verification_reference",
            "verified_at",
            "owner",
            "is_active",
            "lifecycle_status",
            "quality_score",
            "created_at",
            "updated_at",
        )
        export_order = fields

    def before_save_instance(self, instance, row, **kwargs):
        super().before_save_instance(instance, row, **kwargs)
        instance._generate_slug = not instance.slug

    def do_instance_save(self, instance, is_create):
        if getattr(instance, "_generate_slug", False):
            save_business_with_unique_slug(instance)
        else:
            instance.save()
