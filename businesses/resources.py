from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from accounts.models import CustomUser

from .models import Business, unique_business_slug
from simudza.import_export_mixins import ImportUserMixin, VerificationLevelMixin


class BusinessResource(ImportUserMixin, VerificationLevelMixin, resources.ModelResource):
    owner = fields.Field(
        column_name="owner",
        attribute="owner",
        widget=ForeignKeyWidget(CustomUser, "username"),
    )

    class Meta:
        model = Business
        import_id_fields = ("slug",)
        skip_unchanged = True
        fields = (
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
        )
        export_order = fields

    def before_save_instance(self, instance, row, **kwargs):
        super().before_save_instance(instance, row, **kwargs)
        if not instance.slug:
            instance.slug = unique_business_slug(
                instance.name or "business",
                exclude_pk=instance.pk,
            )
