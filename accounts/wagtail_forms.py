from django import forms
from wagtail.admin.widgets import AdminDateInput
from wagtail.images.widgets import AdminImageChooser
from wagtail.users.forms import UserCreationForm, UserEditForm

PROFILE_FIELDS = (
    "phone_number",
    "dob",
    "sex",
    "physical_address",
    "pic",
    "email_verified",
)

PROFILE_WIDGETS = {
    "dob": AdminDateInput,
    "physical_address": forms.Textarea(attrs={"rows": 3}),
    "pic": AdminImageChooser,
}


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields | set(PROFILE_FIELDS)
        widgets = {**UserCreationForm.Meta.widgets, **PROFILE_WIDGETS}


class CustomUserEditForm(UserEditForm):
    class Meta(UserEditForm.Meta):
        fields = UserEditForm.Meta.fields | set(PROFILE_FIELDS)
        widgets = {**UserEditForm.Meta.widgets, **PROFILE_WIDGETS}
