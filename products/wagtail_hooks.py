from wagtail import hooks
from wagtail.admin.viewsets.base import ViewSetGroup

from categories.viewsets import CategoryViewSet

from .viewsets import ProductViewSet, product_chooser_viewset


class CatalogueViewSetGroup(ViewSetGroup):
    menu_label = "Catalogue"
    menu_icon = "tag"
    menu_order = 610
    items = (
        ProductViewSet,
        CategoryViewSet,
    )


@hooks.register("register_admin_viewset")
def register_catalogue_viewset_group():
    return CatalogueViewSetGroup()


@hooks.register("register_admin_viewset")
def register_product_chooser_viewset():
    return product_chooser_viewset


hooks.register("register_bulk_action", ProductViewSet.bulk_edit_action)
hooks.register("register_bulk_action", ProductViewSet.bulk_delete_action)
