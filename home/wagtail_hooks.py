from django.utils.safestring import mark_safe
from wagtail import hooks


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
