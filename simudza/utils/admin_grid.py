from django import forms
from django.forms import Media
from wagtail.admin.panels import FieldRowPanel, MultiFieldPanel

DEFAULT_CHARS = 30
DATE_CHARS = 20
CHECKBOX_CHARS = 12
CHOICE_PADDING_CHARS = 6


class GridRow(FieldRowPanel):
    """Fields that share a row inside a GridPanel; stacks when narrow."""


def _field_chars(bound_field):
    field = bound_field.field
    widget = field.widget
    if isinstance(widget, forms.CheckboxInput):
        return CHECKBOX_CHARS
    if isinstance(widget, (forms.DateInput, forms.DateTimeInput)):
        return DATE_CHARS
    max_length = getattr(field, "max_length", None)
    if max_length:
        return max_length
    if isinstance(field, forms.TypedChoiceField) or (
        isinstance(field, forms.ChoiceField)
        and not isinstance(field, forms.ModelChoiceField)
    ):
        labels = [str(label) for _, label in field.choices]
        if labels:
            return max(len(label) for label in labels) + CHOICE_PADDING_CHARS
    return DEFAULT_CHARS


def _cell(child):
    bound_field = getattr(child, "bound_field", None)
    if bound_field is None:
        return {"child": child, "chars": DEFAULT_CHARS, "wide": True}
    wide = isinstance(bound_field.field.widget, forms.Textarea)
    return {"child": child, "chars": _field_chars(bound_field), "wide": wide}


class GridPanel(MultiFieldPanel):
    """MultiFieldPanel laid out as a responsive grid sized by each field's length."""

    class BoundPanel(MultiFieldPanel.BoundPanel):
        template_name = "admin_form_grid/grid_panel.html"

        @property
        def cells(self):
            rows = []
            for child in self.visible_children:
                if isinstance(child.panel, GridRow):
                    rows.append(
                        {"pair": [_cell(item) for item in child.visible_children]}
                    )
                else:
                    rows.append(_cell(child))
            return rows

        @property
        def media(self):
            return super().media + Media(
                css={"all": ["css/admin_form_grid.css"]}
            )
