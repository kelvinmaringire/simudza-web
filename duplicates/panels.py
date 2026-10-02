from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import Panel

from .models import DuplicateFlag

EDIT_URL_NAMES = {
    DuplicateFlag.Kind.BUSINESS: "business:edit",
    DuplicateFlag.Kind.PRODUCT: "product:edit",
}


def _edit_link(kind, obj):
    return format_html(
        '<a href="{}">{}</a>', reverse(EDIT_URL_NAMES[kind], args=[obj.pk]), obj
    )


def _product_rows(product):
    variants = "; ".join(
        " · ".join(
            part
            for part in (
                v.label,
                f"SKU {v.sku}" if v.sku else "",
                f"barcode {v.barcode}" if v.barcode else "",
            )
            if part
        )
        for v in product.variants.all()
    )
    return [
        (_("Business"), product.business),
        (_("Brand"), product.brand_name),
        (_("Category"), product.category),
        (_("Status"), product.get_status_display()),
        (_("Variants"), variants),
        (_("Image"), product.image),
    ]


def _business_rows(business):
    return [
        (_("Type"), business.get_business_type_display()),
        (_("Website"), business.website),
        (_("Email"), business.email),
        (_("Phone"), business.phone),
        (_("Town / city"), business.town_or_city),
        (_("Owner"), business.owner),
        (_("Active"), _("Yes") if business.is_active else _("No")),
    ]


class DuplicatePairPanel(Panel):
    """Side-by-side comparison of the two flagged listings."""

    class BoundPanel(Panel.BoundPanel):
        def render_html(self, parent_context):
            flag = self.instance
            left, right = flag.left, flag.right
            rows_for = (
                _business_rows if flag.kind == DuplicateFlag.Kind.BUSINESS else _product_rows
            )
            left_rows, right_rows = rows_for(left), rows_for(right)
            comparison = format_html_join(
                "",
                "<tr><th>{}</th><td>{}</td><td>{}</td></tr>",
                (
                    (label, a or "—", b or "—")
                    for (label, a), (_label, b) in zip(left_rows, right_rows)
                ),
            )
            reasons = format_html_join(
                "",
                "<li><strong>{}</strong> {} <span class='help-block'>+{}</span></li>",
                (
                    (r.get("label", ""), r.get("detail", ""), r.get("points", 0))
                    for r in flag.reasons or []
                ),
            )
            return format_html(
                "<p>{intro}</p>"
                "<table class='listing'><thead><tr><th></th><th>{left}</th>"
                "<th>{right}</th></tr></thead><tbody>{rows}</tbody></table>"
                "<h3>{why} — {score}/100</h3><ul>{reasons}</ul>",
                intro=_(
                    "Decide whether these listings describe the same real-world "
                    "entity. Saving a decision does not change either listing."
                ),
                left=_edit_link(flag.kind, left),
                right=_edit_link(flag.kind, right),
                rows=comparison,
                why=_("Why this was flagged"),
                score=flag.score,
                reasons=reasons,
            )


class PossibleDuplicatesPanel(Panel):
    """Shown on business/product edit pages: flags involving this record."""

    class BoundPanel(Panel.BoundPanel):
        def render_html(self, parent_context):
            instance = self.instance
            if not instance or not instance.pk:
                return format_html(
                    '<p class="help-block">{}</p>',
                    _("Duplicate checks run after the record is saved."),
                )
            flags = (
                DuplicateFlag.objects.for_object(instance)
                .exclude(status=DuplicateFlag.Status.DISTINCT)
                .select_related("business_a", "business_b", "product_a", "product_b")
            )
            if not flags:
                return format_html(
                    '<p class="help-block">{}</p>', _("No possible duplicates found.")
                )
            rows = format_html_join(
                "",
                "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td>"
                "<td><a href='{}'>{}</a></td></tr>",
                (
                    (
                        _edit_link(flag.kind, flag.other(instance)),
                        flag.score,
                        flag.reason_summary,
                        flag.get_status_display(),
                        reverse("duplicate_flag:edit", args=[flag.pk]),
                        _("Review"),
                    )
                    for flag in flags
                ),
            )
            return format_html(
                "<table class='listing'><thead><tr><th>{}</th><th>{}</th>"
                "<th>{}</th><th>{}</th><th></th></tr></thead><tbody>{}</tbody></table>",
                _("Possible duplicate of"),
                _("Score"),
                _("Signals"),
                _("Status"),
                rows,
            )
