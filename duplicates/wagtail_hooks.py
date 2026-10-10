from wagtail import hooks

from .viewsets import DataQualityViewSetGroup


@hooks.register("register_admin_viewset")
def register_data_quality_viewset_group():
    return DataQualityViewSetGroup()
