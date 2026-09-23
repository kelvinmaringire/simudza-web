from wagtail import hooks

from .viewsets import CategoryViewSet, category_chooser_viewset


@hooks.register("register_admin_viewset")
def register_category_viewset():
    return CategoryViewSet()


@hooks.register("register_admin_viewset")
def register_category_chooser_viewset():
    return category_chooser_viewset
