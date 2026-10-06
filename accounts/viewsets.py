from wagtail.users.views.users import UserViewSet as WagtailUserViewSet

from simudza.utils.admin_import_export import ImportExportViewSetMixin

from .resources import CustomUserResource
from .wagtail_forms import CustomUserCreationForm, CustomUserEditForm


class UserViewSet(ImportExportViewSetMixin, WagtailUserViewSet):
    resource_class = CustomUserResource
    create_template_name = "accounts/wagtail/user_create.html"
    edit_template_name = "accounts/wagtail/user_edit.html"

    def get_form_class(self, for_update=False):
        if for_update:
            return CustomUserEditForm
        return CustomUserCreationForm
