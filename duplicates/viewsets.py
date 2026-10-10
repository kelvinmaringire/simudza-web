from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import FieldPanel, ObjectList
from wagtail.admin.ui.tables import Column, DateColumn
from wagtail.admin.viewsets.base import ViewSetGroup
from wagtail.admin.viewsets.model import ModelViewSet

from .forms import DuplicateReviewForm
from .models import DuplicateFlag
from .panels import DuplicatePairPanel


class DuplicateFlagViewSet(ModelViewSet):
    model = DuplicateFlag

    name = "duplicate_flag"
    menu_label = _("Possible duplicates")
    menu_icon = "copy"
    add_to_admin_menu = False

    add_view_enabled = False
    copy_view_enabled = False
    delete_view_enabled = False
    inspect_view_enabled = True

    list_display = [
        Column("left", label=_("Listing"), accessor="left"),
        Column("right", label=_("Possible duplicate of"), accessor="right"),
        Column("kind", label=_("Type"), accessor="get_kind_display"),
        Column("score", label=_("Score"), sort_key="score"),
        Column("reason_summary", label=_("Signals"), accessor="reason_summary"),
        Column("status", label=_("Status"), accessor="get_status_display"),
        DateColumn("last_detected_at", label=_("Last detected"), sort_key="last_detected_at"),
    ]

    list_filter = ["status", "kind", "reviewed_by"]

    search_fields = [
        "business_a__name",
        "business_b__name",
        "product_a__name",
        "product_b__name",
        "review_notes",
    ]

    list_export = [
        "kind",
        "left",
        "right",
        "score",
        "reason_summary",
        "status",
        "review_notes",
        "reviewed_by",
        "reviewed_at",
        "detected_at",
        "last_detected_at",
    ]
    export_filename = "possible-duplicates"

    edit_handler = ObjectList(
        [
            DuplicatePairPanel(heading=_("Compare listings")),
            FieldPanel("status"),
            FieldPanel("review_notes"),
        ],
        base_form_class=DuplicateReviewForm,
    )

    inspect_view_fields = [
        "kind",
        "business_a",
        "business_b",
        "product_a",
        "product_b",
        "score",
        "reasons",
        "status",
        "review_notes",
        "reviewed_by",
        "reviewed_at",
        "detected_at",
        "last_detected_at",
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("business_a", "business_b", "product_a", "product_b")
        )


class DataQualityViewSetGroup(ViewSetGroup):
    """Sidebar group; the data-quality queues page joins via submenu_hook."""

    menu_label = _("Data quality")
    menu_icon = "warning"
    menu_order = 650
    submenu_hook = "register_data_quality_menu_item"
    items = (DuplicateFlagViewSet,)
