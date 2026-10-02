from wagtail import hooks

from .viewsets import ProductVariantViewSet, ProductViewSet, product_chooser_viewset


@hooks.register("register_admin_viewset")
def register_product_viewset():
    return ProductViewSet()


@hooks.register("register_admin_viewset")
def register_product_variant_viewset():
    return ProductVariantViewSet()


@hooks.register("register_admin_viewset")
def register_product_chooser_viewset():
    return product_chooser_viewset


hooks.register("register_bulk_action", ProductViewSet.bulk_edit_action)
hooks.register("register_bulk_action", ProductVariantViewSet.bulk_edit_action)
