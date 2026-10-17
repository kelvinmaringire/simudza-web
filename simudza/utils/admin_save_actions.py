"""
Django-admin style footer actions for Wagtail ModelViewSets:
"Save" (back to the listing), "Save and continue editing", "Save and create new",
and "Delete" on edit.
"""

from django.urls import NoReverseMatch, reverse
from wagtail.admin.views.generic.models import CreateView, EditView

CONTINUE_PARAM = "_continue"
ADD_ANOTHER_PARAM = "_addanother"


class SaveAndContinueMixin:
    def get_add_another_url(self):
        namespace = self.edit_url_name.rsplit(":", 1)[0]
        return reverse(f"{namespace}:add")

    def get_success_url(self):
        if CONTINUE_PARAM in self.request.POST:
            return self.get_edit_url()
        if ADD_ANOTHER_PARAM in self.request.POST:
            return self.get_add_another_url()
        return super().get_success_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        can_add = self.user_has_permission("add")
        if can_add:
            # Hide "Save and create new" when this model has no add route
            # (e.g. inventory/offers are created with product variants).
            try:
                self.get_add_another_url()
            except NoReverseMatch:
                can_add = False
        context["can_add"] = can_add
        return context


class SaveActionsCreateView(SaveAndContinueMixin, CreateView):
    template_name = "admin_save_actions/create.html"


class SaveActionsEditView(SaveAndContinueMixin, EditView):
    template_name = "admin_save_actions/edit.html"


class SaveActionsViewSetMixin:
    add_view_class = SaveActionsCreateView
    edit_view_class = SaveActionsEditView
