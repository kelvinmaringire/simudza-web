from wagtail.admin.forms import WagtailAdminModelForm

from .models import DuplicateFlag
from .services import review_flag


class DuplicateReviewForm(WagtailAdminModelForm):
    class Meta:
        model = DuplicateFlag
        fields = ["status", "review_notes"]

    def save(self, commit=True):
        flag = super().save(commit=False)
        if commit:
            review_flag(
                flag,
                status=self.cleaned_data["status"],
                user=self.for_user,
                notes=self.cleaned_data.get("review_notes", ""),
            )
        return flag
