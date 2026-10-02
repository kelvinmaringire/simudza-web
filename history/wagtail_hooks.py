from wagtail import hooks

from .viewsets import ChangeLogViewSet


@hooks.register("register_admin_viewset")
def register_change_log_viewset():
    return ChangeLogViewSet()
