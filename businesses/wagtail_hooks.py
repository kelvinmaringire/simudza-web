from wagtail import hooks

from .viewsets import BusinessViewSet, business_chooser_viewset


@hooks.register("register_admin_viewset")
def register_business_viewset():
    return BusinessViewSet()


@hooks.register("register_admin_viewset")
def register_business_chooser_viewset():
    return business_chooser_viewset
