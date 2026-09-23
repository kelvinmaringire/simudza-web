from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.forms.models import formfield_for_dbfield

from .models import DirectoryListing


class DirectoryListingForm(WagtailAdminModelForm):
    class Meta:
        model = DirectoryListing
        # Required so Wagtail widget overrides are applied.
        formfield_callback = formfield_for_dbfield
        fields = [
            "featured",
            "show_in_directory",
        ]
