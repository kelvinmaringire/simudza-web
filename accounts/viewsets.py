from wagtail.users.views.users import UserViewSet as WagtailUserViewSet

from simudza.admin_import_export import ImportExportViewSetMixin

from .resources import CustomUserResource


class UserViewSet(ImportExportViewSetMixin, WagtailUserViewSet):
    resource_class = CustomUserResource
