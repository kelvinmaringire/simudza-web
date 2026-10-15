from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import InlinePanel, Panel


class CollapsedInlinePanel(InlinePanel):
    """Saved children are titled by the related model's ``label`` and start collapsed; new ones stay open."""

    class BoundPanel(InlinePanel.BoundPanel):
        template_name = "products/panels/collapsed_inline_panel.html"


class DataQualityPanel(Panel):
    class BoundPanel(Panel.BoundPanel):
        def render_html(self, parent_context):
            instance = self.instance
            if not instance or not instance.pk:
                return format_html(
                    "<p class=\"help-block\">{}</p>",
                    _("Save the product first to see data quality."),
                )

            from .quality import ISSUE_LABELS, evaluate_product

            report = evaluate_product(instance)
            check_rows = format_html_join(
                "",
                "<li>{} {}</li>",
                (
                    (
                        "✓" if c.passed else "✗",
                        c.label,
                    )
                    for c in report.checks
                ),
            )
            issue_rows = ""
            if report.issues:
                issue_items = []
                for code in report.issues:
                    label = ISSUE_LABELS.get(code, code)
                    if code == "duplicate_suspected":
                        url = reverse("duplicate_flag:index") + "?kind=product"
                        issue_items.append(
                            format_html('<li><a href="{}">{}</a></li>', url, label)
                        )
                    elif code == "customer_reported":
                        url = reverse("product_review:index")
                        issue_items.append(
                            format_html('<li><a href="{}">{}</a></li>', url, label)
                        )
                    else:
                        issue_items.append(format_html("<li>{}</li>", label))
                issue_rows = format_html(
                    "<h4>{}</h4><ul>{}</ul>",
                    _("Needs attention"),
                    format_html_join("", "{}", ((item,) for item in issue_items)),
                )

            return format_html(
                '<section class="data-quality-panel">'
                "<p><strong>{}</strong></p>"
                "<ul>{}</ul>"
                "{}"
                "</section>",
                _("Data quality: %(score)s/%(max)s")
                % {"score": report.score, "max": report.max_score},
                check_rows,
                issue_rows,
            )

