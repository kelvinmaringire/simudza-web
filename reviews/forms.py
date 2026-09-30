from django.core.exceptions import ValidationError
from django.utils import timezone
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.forms.models import formfield_for_dbfield

from .models import BusinessReview, ProductReview, ReportStatus


class ProductReviewForm(WagtailAdminModelForm):
    class Meta:
        model = ProductReview
        formfield_callback = formfield_for_dbfield
        fields = [
            "user",
            "product",
            "rating",
            "title",
            "body",
            "reason",
            "status",
            "guest_name",
            "guest_email",
            "resolved_at",
            "is_published",
        ]

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if rating is not None and not 1 <= rating <= 5:
            raise ValidationError("Rating must be between 1 and 5.")
        return rating

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.status != ReportStatus.OPEN and not instance.resolved_at:
            instance.resolved_at = timezone.now()
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class BusinessReviewForm(WagtailAdminModelForm):
    class Meta:
        model = BusinessReview
        formfield_callback = formfield_for_dbfield
        fields = [
            "user",
            "business",
            "rating",
            "title",
            "body",
            "reason",
            "status",
            "guest_name",
            "guest_email",
            "resolved_at",
            "is_published",
        ]

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if rating is not None and not 1 <= rating <= 5:
            raise ValidationError("Rating must be between 1 and 5.")
        return rating

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.status != ReportStatus.OPEN and not instance.resolved_at:
            instance.resolved_at = timezone.now()
        if commit:
            instance.save()
            self.save_m2m()
        return instance
