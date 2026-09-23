from django.utils.text import slugify
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.forms.models import formfield_for_dbfield

from .models import Category


class CategoryForm(WagtailAdminModelForm):
    class Meta:
        model = Category
        # Required so Wagtail widget overrides are applied. Defining Meta
        # without this drops the parent formfield_callback.
        formfield_callback = formfield_for_dbfield
        fields = [
            "name",
            "description",
            "parent",
            "is_active",
            "sort_order",
        ]

    def save(self, commit=True):
        category = super().save(commit=False)

        category.slug = slugify(category.name)

        if commit:
            category.save()

        return category
