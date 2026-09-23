from wagtail import hooks

from .viewsets import ReviewsViewSetGroup


@hooks.register("register_admin_viewset")
def register_reviews_viewset_group():
    return ReviewsViewSetGroup()
