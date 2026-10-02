from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from wagtail.admin.views.generic.base import WagtailAdminTemplateMixin

from businesses.quality import ISSUE_LABELS as BUSINESS_ISSUE_LABELS
from businesses.quality import issue_counts as business_issue_counts
from businesses.quality import score_band_counts as business_score_bands
from categories.quality import ISSUE_LABELS as CATEGORY_ISSUE_LABELS
from categories.quality import issue_counts as category_issue_counts
from categories.quality import needing_attention_count as categories_needing_attention
from products.quality import ISSUE_LABELS as PRODUCT_ISSUE_LABELS
from products.quality import issue_counts as product_issue_counts
from products.quality import score_band_counts as product_score_bands


def user_can_view_data_quality(user):
    if not user.is_active:
        return False
    if user.is_superuser:
        return True
    perms = user.get_all_permissions()
    return (
        "products.view_product" in perms or "businesses.view_business" in perms
    )


class DataQualityIndexView(WagtailAdminTemplateMixin, TemplateView):
    template_name = "admin_data_quality/index.html"
    page_title = _("Data quality")

    def dispatch(self, request, *args, **kwargs):
        if not user_can_view_data_quality(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product_counts = product_issue_counts()
        business_counts = business_issue_counts()
        category_counts = category_issue_counts()
        context.update(
            {
                "product_issue_rows": [
                    (PRODUCT_ISSUE_LABELS[code], product_counts.get(code, 0), code)
                    for code in PRODUCT_ISSUE_LABELS
                ],
                "business_issue_rows": [
                    (BUSINESS_ISSUE_LABELS[code], business_counts.get(code, 0), code)
                    for code in BUSINESS_ISSUE_LABELS
                ],
                "category_issue_rows": [
                    (CATEGORY_ISSUE_LABELS[code], category_counts.get(code, 0), code)
                    for code in CATEGORY_ISSUE_LABELS
                ],
                "product_score_bands": product_score_bands(),
                "business_score_bands": business_score_bands(),
                "product_index_url": reverse("product:index"),
                "business_index_url": reverse("business:index"),
                "category_index_url": reverse("category:index"),
                "categories_needing_attention": categories_needing_attention(),
            }
        )
        return context
