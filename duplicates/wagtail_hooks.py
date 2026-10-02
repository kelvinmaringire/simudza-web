from wagtail import hooks

from .viewsets import DuplicateFlagViewSet


@hooks.register("register_admin_viewset")
def register_duplicate_flag_viewset():
    return DuplicateFlagViewSet()
