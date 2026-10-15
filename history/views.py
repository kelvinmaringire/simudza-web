from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from wagtail.admin.views.generic.base import WagtailAdminTemplateMixin

from .models import ChangeLog
from .undo import UndoError, batch_entries, undo_blocker, undo_entries


def _can_change(user, entry):
    model = entry.content_type.model_class()
    if model is None:
        return False
    opts = model._meta
    return user.has_perm(f"{opts.app_label}.change_{opts.model_name}")


class ChangeLogUndoView(WagtailAdminTemplateMixin, TemplateView):
    template_name = "history/admin/undo.html"
    page_title = _("Undo change")
    header_icon = "history"

    def dispatch(self, request, *args, **kwargs):
        self.entry = get_object_or_404(
            ChangeLog.objects.select_related("content_type"), pk=kwargs["pk"]
        )
        self.batch = batch_entries(self.entry)
        for item in self.batch:
            if not _can_change(request.user, item):
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_page_subtitle(self):
        return self.entry.object_repr

    def get_breadcrumbs_items(self):
        return self.breadcrumbs_items + [
            {"url": reverse("change_log:index"), "label": _("Change history")},
            {"url": reverse("change_log:inspect", args=[self.entry.pk]), "label": str(self.entry)},
            {"url": "", "label": _("Undo")},
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = [(item, undo_blocker(item)) for item in self.batch]
        context.update(
            entry=self.entry,
            entry_blocker=undo_blocker(self.entry),
            rows=rows,
            batch_undoable=len(rows) > 1 and not any(blocker for _item, blocker in rows),
            batch_size=len(rows),
            back_url=reverse("change_log:inspect", args=[self.entry.pk]),
        )
        return context

    def post(self, request, *args, **kwargs):
        entries = self.batch if request.POST.get("scope") == "batch" else [self.entry]
        try:
            count = undo_entries(entries, user=request.user, reason=request.POST.get("reason", "").strip())
        except UndoError as exc:
            messages.error(request, str(exc))
            return redirect("change_log:undo", pk=self.entry.pk)
        messages.success(
            request,
            _("Undid %(count)d change(s) to %(obj)s.") % {"count": count, "obj": self.entry.object_repr},
        )
        return redirect("change_log:inspect", pk=self.entry.pk)
