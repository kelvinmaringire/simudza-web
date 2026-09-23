from django.core.exceptions import ValidationError
from wagtail.admin.forms import WagtailAdminModelForm
from wagtail.admin.forms.models import formfield_for_dbfield

from .models import BusinessReview, ProductReview


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
            "is_published",
        ]

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if rating is not None and not 1 <= rating <= 5:
            raise ValidationError("Rating must be between 1 and 5.")
        return rating


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
            "is_published",
        ]

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if rating is not None and not 1 <= rating <= 5:
            raise ValidationError("Rating must be between 1 and 5.")
        return rating
