from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import Panel

from .quality import category_issue_labels


class CategoryIssuesPanel(Panel):
    class BoundPanel(Panel.BoundPanel):
        def render_html(self, parent_context):
            instance = self.instance
            if not instance or not instance.pk:
                return format_html(
                    "<p class=\"help-block\">{}</p>",
                    _("Save the category first to see data quality notes."),
                )

            labels = category_issue_labels(instance)
            if not labels:
                return format_html(
                    "<p class=\"help-block\">{}</p>",
                    _("No attention items for this category."),
                )

            rows = format_html_join(
                "",
                "<li>{}</li>",
                ((label,) for label in labels),
            )
            return format_html(
                "<section><h4>{}</h4><ul>{}</ul></section>",
                _("Needs attention"),
                rows,
            )
