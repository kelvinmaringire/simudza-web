"""
Wagtail bulk delete for ModelViewSet listings (Wagtail only ships one for snippets).
"""

from __future__ import annotations

from django.contrib.admin.utils import quote
from django.db.models import ProtectedError
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse
from django.utils.functional import classproperty
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from wagtail.admin import messages
from wagtail.admin.admin_url_finder import AdminURLFinder
from wagtail.admin.views.bulk_action import BulkAction
from wagtail.admin.views.bulk_action.mixins import ReferenceIndexMixin
from wagtail.permissions import ModelPermissionPolicy


def _protected_summary(exc: ProtectedError) -> str:
    labels = sorted(
        {str(capfirst(obj._meta.verbose_name_plural)) for obj in exc.protected_objects}
    )
    return ", ".join(labels)


def make_bulk_delete_action(model, url_namespace: str | None = None):
    permission_policy = ModelPermissionPolicy(model)

    class ModelBulkDeleteAction(ReferenceIndexMixin, BulkAction):
        display_name = _("Delete")
        action_type = "delete"
        aria_label = _("Delete selected items")
        template_name = "wagtailsnippets/bulk_actions/confirm_bulk_delete.html"
        action_priority = 30
        classes = {"serious"}

        @classproperty
        def models(cls):
            return [model]

        def check_perm(self, obj):
            return permission_policy.user_has_permission_for_instance(
                self.request.user, "delete", obj
            )

        def get_all_objects_in_listing_query(self, parent_id):
            return model._default_manager.order_by("pk").values_list("pk", flat=True)

        def object_context(self, obj):
            return {
                **super().object_context(obj),
                "edit_url": AdminURLFinder(self.request.user).get_edit_url(obj),
            }

        def get_context_data(self, **kwargs):
            return super().get_context_data(header_icon="bin", **kwargs)

        def get_usage_url(self, obj):
            if not url_namespace:
                return None
            try:
                url = reverse(f"{url_namespace}:usage", args=(quote(obj.pk),))
            except NoReverseMatch:
                return None
            return url + "?describe_on_delete=1"

        @classmethod
        def execute_action(cls, objects, **kwargs):
            model._default_manager.filter(pk__in=[obj.pk for obj in objects]).delete()
            return len(objects), 0

        def get_success_message(self, num_parent_objects, num_child_objects):
            return ngettext(
                "%(count)d %(model_name)s deleted.",
                "%(count)d %(model_name_plural)s deleted.",
                num_parent_objects,
            ) % {
                "count": num_parent_objects,
                "model_name": model._meta.verbose_name,
                "model_name_plural": model._meta.verbose_name_plural,
            }

        def _blocked(self, related):
            messages.error(
                self.request,
                _(
                    "Nothing was deleted: some selected items are still used by "
                    "%(related)s. Reassign or remove those first."
                )
                % {"related": related},
            )
            return redirect(self.next_url)

        def prepare_action(self, objects, objects_without_access):
            if self.is_protected:
                return self._blocked(_("other records"))
            return super().prepare_action(objects, objects_without_access)

        def form_valid(self, form):
            try:
                return super().form_valid(form)
            except ProtectedError as exc:
                return self._blocked(_protected_summary(exc))

    return ModelBulkDeleteAction
