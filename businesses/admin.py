from django.contrib import admin, messages

from .models import Business, ManufacturerSubmission, RetailLocation
from .services import apply_submission


@admin.register(RetailLocation)
class RetailLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "town_or_city", "is_active")
    list_filter = ("is_active", "town_or_city")
    search_fields = ("name", "business__name", "town_or_city", "address")


@admin.register(ManufacturerSubmission)
class ManufacturerSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "kind",
        "status",
        "submitted_by",
        "business",
        "product",
        "created_at",
    )
    list_filter = ("kind", "status")
    search_fields = (
        "company_name",
        "product_name",
        "location_name",
        "submitted_by__username",
        "submitted_by__email",
    )
    readonly_fields = ("created_at", "applied_at")
    actions = ("apply_selected_submissions",)

    @admin.action(description="Apply selected submissions")
    def apply_selected_submissions(self, request, queryset):
        applied = 0
        for submission in queryset.exclude(
            status=ManufacturerSubmission.Status.APPLIED,
        ):
            try:
                apply_submission(submission, reviewer=request.user)
                applied += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"Could not apply submission {submission.pk}: {exc}",
                    level=messages.ERROR,
                )
        if applied:
            self.message_user(
                request,
                f"Applied {applied} submission(s).",
                level=messages.SUCCESS,
            )
