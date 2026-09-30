"""
Wagtail ModelViewSet mixin: CSV/XLSX export and import via django-import-export.
"""

from __future__ import annotations

import uuid
from datetime import date

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
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
FORMAT_CHOICES = {
    "csv": CSV(),
    "xlsx": XLSX(),
}

IMPORT_SESSION_KEY = "simudza_import_export_pending"


def _load_dataset(uploaded_file, fmt: str) -> Dataset:
    format_obj = FORMAT_CHOICES.get(fmt)
    if format_obj is None:
        raise ValueError(f"Unsupported format: {fmt}")
    raw = uploaded_file.read()
    if isinstance(raw, bytes) and fmt == "csv":
        raw = raw.decode("utf-8-sig")
    return format_obj.create_dataset(raw)


def _export_filename(model, fmt: str) -> str:
    base = model._meta.model_name
    stamp = date.today().strftime("%Y%m%d")
    return f"{base}-{stamp}.{fmt}"


class ImportExportIndexViewMixin:
    """Adds import/export header buttons to a Wagtail admin index."""

    resource_class = None
    export_url_name = None
    import_url_name = None

    def get_header_more_buttons(self):
        buttons = list(super().get_header_more_buttons())
        user = self.request.user
        policy = self.permission_policy

        if (
            self.resource_class
            and self.export_url_name
            and policy
            and policy.user_has_permission(user, "view")
        ):
            buttons.extend(
                [
                    Button(
                        _("Export CSV"),
                        url=reverse(self.export_url_name, kwargs={"fmt": "csv"}),
                        icon_name="download",
                        priority=80,
                    ),
                    Button(
                        _("Export Excel"),
                        url=reverse(self.export_url_name, kwargs={"fmt": "xlsx"}),
                        icon_name="download",
                        priority=81,
                    ),
                ]
            )

        if (
            self.resource_class
            and self.import_url_name
            and policy
            and policy.user_has_permission(user, "add")
        ):
            buttons.extend(
                [
                    Button(
                        _("Import CSV"),
                        url=reverse(self.import_url_name, kwargs={"fmt": "csv"}),
                        icon_name="upload",
                        priority=82,
                    ),
                    Button(
                        _("Import Excel"),
                        url=reverse(self.import_url_name, kwargs={"fmt": "xlsx"}),
                        icon_name="upload",
                        priority=83,
                    ),
                ]
            )

        return buttons


def import_export_index_view_class(base_index=IndexView):
    class ImportExportIndexView(ImportExportIndexViewMixin, base_index):
        pass

    return ImportExportIndexView


class AdminExportView(PermissionCheckedMixin, View):
    model = None
    resource_class = None
    permission_required = "view"
    index_url_name = None

    def get(self, request, fmt):
        fmt = fmt.lower()
        if fmt not in FORMAT_CHOICES:
            raise PermissionDenied
        resource = self.resource_class()
        queryset = self.model._default_manager.all()
        dataset = resource.export(queryset)
        format_obj = FORMAT_CHOICES[fmt]
        data = format_obj.export_data(dataset)
        content_type = format_obj.get_content_type()
        response = HttpResponse(data, content_type=content_type)
        response["Content-Disposition"] = (
            f'attachment; filename="{_export_filename(self.model, fmt)}"'
        )
        return response


class AdminImportView(WagtailAdminTemplateMixin, PermissionCheckedMixin, TemplateView):
    model = None
    resource_class = None
    permission_required = "add"
    template_name = "admin_import_export/import_form.html"
    index_url_name = None
    import_url_name = None
    import_confirm_url_name = None

    def dispatch(self, request, *args, **kwargs):
        self.import_fmt = kwargs.get("fmt", "").lower()
        if self.import_fmt not in FORMAT_CHOICES:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "format": self.import_fmt,
                "model_verbose_name": self.model._meta.verbose_name_plural,
                "index_url_name": self.index_url_name,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        fmt = self.import_fmt
        upload = request.FILES.get("import_file")
        if not upload:
            messages.error(request, _("Choose a file to import."))
            return redirect(reverse(self.import_url_name, kwargs={"fmt": fmt}))

        raw = upload.read()
        try:
            dataset = _load_dataset(ContentFile(raw), fmt)
        except Exception as exc:
            messages.error(request, _("Could not read file: %(error)s") % {"error": exc})
            return redirect(reverse(self.import_url_name, kwargs={"fmt": fmt}))

        resource = self.resource_class()
        result = resource.import_data(
            dataset,
            dry_run=True,
            raise_errors=False,
            user=request.user,
        )

        storage = MediaStorage()
        storage.name = f"{uuid.uuid4().hex}.{fmt}"
        storage.save(raw)

        request.session[IMPORT_SESSION_KEY] = {
            "storage_name": storage.name,
            "format": fmt,
        }

        self.template_name = "admin_import_export/import_preview.html"
        context = self.get_context_data()
        context.update(
            {
                "result": result,
                "confirm_url": reverse(
                    self.import_confirm_url_name,
                    kwargs={"fmt": fmt},
                ),
                "error_rows": [
                    row for row in result.rows if getattr(row, "errors", None)
                ],
            }
        )
        return self.render_to_response(context)


class AdminImportConfirmView(PermissionCheckedMixin, View):
    model = None
    resource_class = None
    permission_required = "add"
    index_url_name = None

    def post(self, request, fmt):
        pending = request.session.get(IMPORT_SESSION_KEY)
        if not pending or pending.get("format") != fmt.lower():
            messages.error(request, _("Import session expired. Upload the file again."))
            return redirect(reverse(self.index_url_name))

        storage = MediaStorage()
        storage.name = pending["storage_name"]
        try:
            dataset = _load_dataset(
                ContentFile(storage.read()),
                pending["format"],
            )
        except Exception as exc:
            messages.error(request, _("Could not reload file: %(error)s") % {"error": exc})
            return redirect(reverse(self.index_url_name))

        resource = self.resource_class()
        with transaction.atomic():
            result = resource.import_data(
                dataset,
                dry_run=False,
                raise_errors=False,
                user=request.user,
            )

        try:
            storage.remove()
        except OSError:
            pass
        request.session.pop(IMPORT_SESSION_KEY, None)

        messages.success(
            request,
            _(
                "Import complete: %(new)s new, %(update)s updated, "
                "%(error)s errors, %(skip)s skipped."
            )
            % {
                "new": result.totals.get("new", 0),
                "update": result.totals.get("update", 0),
                "error": result.totals.get("error", 0),
                "skip": result.totals.get("skip", 0),
            },
        )
        return redirect(reverse(self.index_url_name))


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
        from django.urls import path

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

    @property
    def export_view(self):
        return self.construct_view(
            AdminExportView,
            model=self.model,
            resource_class=self.resource_class,
            index_url_name=self.get_url_name("index"),
        )

    @property
    def import_view(self):
        return self.construct_view(
            AdminImportView,
            model=self.model,
            resource_class=self.resource_class,
            index_url_name=self.get_url_name("index"),
            import_url_name=self.get_url_name("import"),
            import_confirm_url_name=self.get_url_name("import_confirm"),
        )

    @property
    def import_confirm_view(self):
        return self.construct_view(
            AdminImportConfirmView,
            model=self.model,
            resource_class=self.resource_class,
            index_url_name=self.get_url_name("index"),
        )
