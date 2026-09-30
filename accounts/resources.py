from import_export import resources

from .models import CustomUser


class CustomUserResource(resources.ModelResource):
    class Meta:
        model = CustomUser
        import_id_fields = ("username",)
        skip_unchanged = True
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "is_active",
            "is_superuser",
            "dob",
            "sex",
            "physical_address",
            "phone_number",
            "email_verified",
            "date_joined",
            "last_login",
        )
        export_order = fields

    def before_save_instance(self, instance, row, **kwargs):
        super().before_save_instance(instance, row, **kwargs)
        if not instance.pk or not instance.password:
            instance.set_unusable_password()
