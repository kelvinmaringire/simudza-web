from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from wagtail.admin.panels import Panel

from .services import changes_for


class ChangeHistoryPanel(Panel):
    class BoundPanel(Panel.BoundPanel):
        def render_html(self, parent_context):
            instance = self.instance
            if not instance or not instance.pk:
                return format_html(
                    '<p class="help-block">{}</p>',
                    _("Save this record first to view change history."),
                )

            rows = changes_for(instance, limit=20)
            if not rows:
                return format_html(
                    '<p class="help-block">{}</p>',
                    _("No changes recorded yet."),
                )

            ct = ContentType.objects.get_for_model(instance, for_concrete_model=False)
            list_url = (
                reverse("change_log:index")
                + f"?content_type_id={ct.pk}&object_id={instance.pk}"
            )

            body = [
                format_html(
                    '<p class="help-block"><a href="{}">{}</a></p>',
                    list_url,
                    _("View all changes"),
                ),
                "<table class='listing'><thead><tr>",
                "<th>Field</th><th>Old</th><th>New</th><th>By</th><th>When</th>",
                "</tr></thead><tbody>",
            ]
            for row in rows:
                body.append(
                    format_html(
                        "<tr><td>{field}</td><td>{old}</td><td>{new}</td>"
                        "<td>{by}</td><td>{when}</td></tr>",
                        field=row.field_label or row.get_action_display(),
                        old=row.old_value or "—",
                        new=row.new_value or "—",
                        by=row.changed_by_repr or "—",
                        when=row.changed_at.strftime("%d %B %Y %H:%M"),
                    )
                )
            body.append("</tbody></table>")
            return mark_safe("".join(str(part) for part in body))
