from django.apps import AppConfig
from wagtail.users.apps import WagtailUsersAppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"


class SimudzaUsersAppConfig(WagtailUsersAppConfig):
    user_viewset = "accounts.viewsets.UserViewSet"
