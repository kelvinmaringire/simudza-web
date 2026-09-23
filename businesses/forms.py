from django.utils.text import slugify
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.forms.models import formfield_for_dbfield

from .models import Business


class BusinessForm(WagtailAdminModelForm):
    class Meta:
        model = Business
        # Required so Wagtail widget overrides (image chooser, date picker)
        # are applied. Defining Meta without this drops the parent callback.
        formfield_callback = formfield_for_dbfield
        fields = [
            "name",
            "business_type",
            "description",
            "logo",
            "website",
            "email",
            "phone",
            "address",
            "city",
            "province",
            "country",
            "verification_status",
            "verified_at",
            "is_active",
        ]

    def save(self, commit=True):
        business = super().save(commit=False)

        business.slug = slugify(business.name)

        # ModelViewSet passes the request user as for_user.
        user = self.for_user
        if (
            not business.owner_id
            and user
            and user.is_authenticated
        ):
            business.owner = user

        if commit:
            business.save()

        return business
