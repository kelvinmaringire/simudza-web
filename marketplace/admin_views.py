from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from wagtail.admin.views.generic.base import WagtailAdminTemplateMixin

from marketplace.cart_analytics import cart_analytics_summary, user_can_view_cart_analytics


class CartAnalyticsIndexView(WagtailAdminTemplateMixin, TemplateView):
    template_name = "marketplace/admin/cart_analytics.html"
    page_title = _("Cart analytics")

    def dispatch(self, request, *args, **kwargs):
        if not user_can_view_cart_analytics(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(cart_analytics_summary())
        return context
