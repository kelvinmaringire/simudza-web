"""
Wagtail ModelViewSet mixin: CSV/XLSX export and import via django-import-export.
"""

from __future__ import annotations

import uuid
from datetime import date

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView
from import_export.formats.base_formats import CSV, XLSX
from import_export.tmp_storages import MediaStorage
from tablib import Dataset
from wagtail.admin.views.generic import WagtailAdminTemplateMixin
from wagtail.admin.views.generic.models import IndexView
from wagtail.admin.views.generic.permissions import PermissionCheckedMixin
from wagtail.admin.widgets.button import Button

from history.context import change_context
from history.models import ChangeLog

FORMAT_CHOICES = {
    "csv": CSV(),
    "xlsx": XLSX(),
}

FORMAT_LABELS = {
    "csv": _("CSV"),
    "xlsx": _("Excel"),
}

IMPORT_SESSION_KEY = "simudza_import_export_pending"


def load_dataset(raw, fmt: str) -> Dataset:
    if fmt == "csv" and isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    return FORMAT_CHOICES[fmt].create_dataset(raw)


def export_filename(model, fmt: str) -> str:
    stamp = date.today().strftime("%Y%m%d")
    return f"{model._meta.model_name}-{stamp}.{fmt}"


class PendingImport:
    """Uploaded file kept in media storage between import preview and confirm."""

    def __init__(self, storage_name: str, fmt: str):
        self.fmt = fmt
        self.storage = MediaStorage()
        self.storage.name = storage_name

    @property
    def name(self) -> str:
        return self.storage.name

    @classmethod
    def create(cls, request, raw, fmt: str) -> PendingImport:
        pending = cls(f"{uuid.uuid4().hex}.{fmt}", fmt)
        pending.storage.save(raw)
        request.session[IMPORT_SESSION_KEY] = {
            "storage_name": pending.name,
            "format": fmt,
        }
        return pending

    @classmethod
    def from_session(cls, request) -> PendingImport | None:
        data = request.session.get(IMPORT_SESSION_KEY)
        if not data:
            return None
        return cls(data["storage_name"], data["format"])

    def load_dataset(self) -> Dataset:
        return load_dataset(self.storage.read(), self.fmt)

    def discard(self, request) -> None:
        try:
            self.storage.remove()
        except OSError:
            pass
        request.session.pop(IMPORT_SESSION_KEY, None)


class FormatMixin:
    """Reads and validates the ``fmt`` URL kwarg into ``self.fmt``."""

    def dispatch(self, request, *args, **kwargs):
        self.fmt = kwargs.get("fmt", "").lower()
        if self.fmt not in FORMAT_CHOICES:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class ImportExportIndexViewMixin:
    """Adds import/export header buttons to a Wagtail admin index."""

    resource_class = None
    export_url_name = None
    import_url_name = None

    def get_header_more_buttons(self):
        buttons = list(super().get_header_more_buttons())
        policy = self.permission_policy
        if not self.resource_class or not policy:
            return buttons

        actions = (
            (self.export_url_name, "view", _("Export %(format)s"), "download", 80),
            (self.import_url_name, "add", _("Import %(format)s"), "upload", 82),
        )
        for url_name, permission, label, icon, priority in actions:
            if not url_name or not policy.user_has_permission(
                self.request.user, permission
            ):
                continue
            for offset, fmt in enumerate(FORMAT_CHOICES):
                buttons.append(
                    Button(
                        label % {"format": FORMAT_LABELS[fmt]},
                        url=reverse(url_name, kwargs={"fmt": fmt}),
                        icon_name=icon,
                        priority=priority + offset,
                    )
                )
        return buttons


def import_export_index_view_class(base_index=IndexView):
    return type(
        "ImportExportIndexView",
        (ImportExportIndexViewMixin, base_index),
        {},
    )


class AdminExportView(FormatMixin, PermissionCheckedMixin, View):
    model = None
    resource_class = None
    permission_required = "view"
    index_url_name = None

    def get(self, request, *args, **kwargs):
        dataset = self.resource_class().export(self.model._default_manager.all())
        format_obj = FORMAT_CHOICES[self.fmt]
        response = HttpResponse(
            format_obj.export_data(dataset),
            content_type=format_obj.get_content_type(),
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{export_filename(self.model, self.fmt)}"'
        )
        return response


class AdminImportView(
    FormatMixin, WagtailAdminTemplateMixin, PermissionCheckedMixin, TemplateView
):
    model = None
    resource_class = None
    permission_required = "add"
    template_name = "admin_import_export/import_form.html"
    preview_template_name = "admin_import_export/import_preview.html"
    index_url_name = None
    import_url_name = None
    import_confirm_url_name = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "format": self.fmt,
                "model_verbose_name": self.model._meta.verbose_name_plural,
                "index_url_name": self.index_url_name,
            }
        )
        return context

    def redirect_to_form(self):
        return redirect(reverse(self.import_url_name, kwargs={"fmt": self.fmt}))

    def post(self, request, *args, **kwargs):
        upload = request.FILES.get("import_file")
        if not upload:
            messages.error(request, _("Choose a file to import."))
            return self.redirect_to_form()

        raw = upload.read()
        try:
            dataset = load_dataset(raw, self.fmt)
        except Exception as exc:
            messages.error(request, _("Could not read file: %(error)s") % {"error": exc})
            return self.redirect_to_form()

        result = self.resource_class().import_data(
            dataset,
            dry_run=True,
            raise_errors=False,
            user=request.user,
        )
        PendingImport.create(request, raw, self.fmt)

        self.template_name = self.preview_template_name
        context = self.get_context_data()
        context.update(
            {
                "result": result,
                "confirm_url": reverse(
                    self.import_confirm_url_name,
                    kwargs={"fmt": self.fmt},
                ),
                "error_rows": [
                    row for row in result.rows if getattr(row, "errors", None)
                ],
            }
        )
        return self.render_to_response(context)


class AdminImportConfirmView(FormatMixin, PermissionCheckedMixin, View):
    model = None
    resource_class = None
    permission_required = "add"
    index_url_name = None

    def post(self, request, *args, **kwargs):
        index_url = reverse(self.index_url_name)
        pending = PendingImport.from_session(request)
        if pending is None or pending.fmt != self.fmt:
            messages.error(request, _("Import session expired. Upload the file again."))
            return redirect(index_url)

        try:
            dataset = pending.load_dataset()
        except Exception as exc:
            messages.error(request, _("Could not reload file: %(error)s") % {"error": exc})
            return redirect(index_url)

        with change_context(
            user=request.user,
            source=ChangeLog.Source.IMPORT,
            reason=f"Import {pending.name}",
        ), transaction.atomic():
            result = self.resource_class().import_data(
                dataset,
                dry_run=False,
                raise_errors=False,
                user=request.user,
            )

        pending.discard(request)

        totals = result.totals
        messages.success(
            request,
            _(
                "Import complete: %(new)s new, %(update)s updated, "
                "%(error)s errors, %(skip)s skipped."
            )
            % {key: totals.get(key, 0) for key in ("new", "update", "error", "skip")},
        )
        return redirect(index_url)


class ImportExportViewSetMixin:
    """
    Mixin for Wagtail ModelViewSet: export/import URLs and index header buttons.
    Set ``resource_class`` on the viewset.
    """

    resource_class = None

    def get_index_view_kwargs(self, **kwargs):
        view_kwargs = super().get_index_view_kwargs(**kwargs)
        view_kwargs.update(
            {
                "resource_class": self.resource_class,
                "export_url_name": self.get_url_name("export"),
                "import_url_name": self.get_url_name("import"),
            }
        )
        return view_kwargs

    @property
    def index_view(self):
        view_class = self.index_view_class
        if self.resource_class:
            view_class = import_export_index_view_class(view_class)
        return self.construct_view(view_class, **self.get_index_view_kwargs())

    def import_export_urlpatterns(self):
        if not self.resource_class:
            return []
        return [
            path("export/<str:fmt>/", self.export_view, name="export"),
            path("import/<str:fmt>/", self.import_view, name="import"),
            path(
                "import/<str:fmt>/confirm/",
                self.import_confirm_view,
                name="import_confirm",
            ),
        ]

    def get_urlpatterns(self):
        patterns = super().get_urlpatterns()
        patterns.extend(self.import_export_urlpatterns())
        return patterns

    def construct_import_export_view(self, view_class, **kwargs):
        return self.construct_view(
            view_class,
            model=self.model,
            resource_class=self.resource_class,
            index_url_name=self.get_url_name("index"),
            **kwargs,
        )

    @property
    def export_view(self):
        return self.construct_import_export_view(AdminExportView)

    @property
    def import_view(self):
        return self.construct_import_export_view(
            AdminImportView,
            import_url_name=self.get_url_name("import"),
            import_confirm_url_name=self.get_url_name("import_confirm"),
        )

    @property
    def import_confirm_view(self):
        return self.construct_import_export_view(AdminImportConfirmView)
