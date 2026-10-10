from django.urls import path, reverse
from django.utils.safestring import mark_safe
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.ui.components import Component

from simudza.utils.admin_data_quality import (
    DataQualityIndexView,
    user_can_view_data_quality,
)
from duplicates.viewsets import DataQualityViewSetGroup
from businesses.quality import (
    listings_needing_attention_count as businesses_needing_attention,
)
from products.quality import (
    listings_needing_attention_count as products_needing_attention,
)


class ViewSitePanel(Component):
    name = "view_site"
    order = 10

    def render_html(self, parent_context=None):
        return mark_safe(
            """
            <section class="w-mb-8">
                <a href="/" class="button button-primary">Go to site home</a>
            </section>
            """
        )


class DataQualityHomePanel(Component):
    order = 15

    def __init__(self, request):
        self.request = request

    def render_html(self, parent_context=None):
        total = products_needing_attention() + businesses_needing_attention()
        url = reverse("simudza_data_quality_index")
        return mark_safe(
            f"""
            <section class="panel summary nice-padding w-mb-8">
                <h2 class="w-h3">Data quality</h2>
                <p>{total} listings need attention.</p>
                <p><a href="{url}" class="button button-secondary">View queues</a></p>
            </section>
            """
        )


@hooks.register("construct_homepage_panels")
def add_home_panels(request, panels):
    panels.insert(0, ViewSitePanel())
    if user_can_view_data_quality(request.user):
        panels.insert(1, DataQualityHomePanel(request))


@hooks.register("register_admin_urls")
def register_data_quality_urls():
    return [
        path(
            "data-quality/",
            DataQualityIndexView.as_view(),
            name="simudza_data_quality_index",
        ),
    ]


@hooks.register(DataQualityViewSetGroup.submenu_hook)
def register_data_quality_menu_item():
    class DataQualityMenuItem(MenuItem):
        def is_shown(self, request):
            return user_can_view_data_quality(request.user)

    return DataQualityMenuItem(
        "Quality queues",
        reverse("simudza_data_quality_index"),
        name="data-quality",
        icon_name="warning",
        order=0,
    )


@hooks.register("insert_global_admin_css")
def simudza_admin_branding_css():
    # Compact branding: full logo when expanded, favicon when collapsed.
    return mark_safe(
        """
        <style>
            .sidebar-custom-branding {
                margin: 0 auto;
                padding: 0.35rem 0.5rem;
                line-height: 0;
            }
            .sidebar-custom-branding .simudza-branding-logo {
                display: block;
                width: 100%;
                max-width: 140px;
                height: auto;
                margin: 0 auto;
            }
            .sidebar-custom-branding .simudza-branding-favicon {
                display: none;
                width: 28px;
                height: 28px;
                margin: 0 auto;
            }
            .sidebar--slim .sidebar-custom-branding {
                margin: 0 auto;
                padding: 0.35rem 0;
            }
            .sidebar--slim .sidebar-custom-branding .simudza-branding-logo {
                display: none;
            }
            .sidebar--slim .sidebar-custom-branding .simudza-branding-favicon {
                display: block;
            }
        </style>
        """
    )
