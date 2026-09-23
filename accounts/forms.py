from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)

User = get_user_model()


class MemberLoginForm(AuthenticationForm):
    """Login form for site members (username or email)."""

    remember_me = forms.BooleanField(
        required=False,
        initial=False,
        label="Remember me",
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": (
            "Please enter a correct username/email and password."
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Username or email"
        self.fields["username"].widget.attrs.update(
            {
                "autocomplete": "username",
                "placeholder": "Username or email",
            }
        )
        self.fields["password"].widget.attrs.update(
            {
                "placeholder": "Password",
            }
        )

    def clean(self):
        username = self.cleaned_data.get("username")
        if username and "@" in username:
            user = User.objects.filter(email__iexact=username.strip()).first()
            if user is not None:
                self.cleaned_data["username"] = user.get_username()
        return super().clean()


class MemberSignUpForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "placeholder": "Email address",
            }
        ),
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "autocomplete": "username",
                "placeholder": "Username",
            }
        )
        self.fields["password1"].widget.attrs.update(
            {
                "autocomplete": "new-password",
                "placeholder": "Password",
            }
        )
        self.fields["password2"].widget.attrs.update(
            {
                "autocomplete": "new-password",
                "placeholder": "Confirm password",
            }
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class MemberPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "Email"
        self.fields["email"].widget.attrs.update(
            {
                "autocomplete": "email",
                "placeholder": "Email address",
            }
        )


class MemberSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].widget.attrs.update(
            {
                "autocomplete": "new-password",
                "placeholder": "New password",
            }
        )
        self.fields["new_password2"].widget.attrs.update(
            {
                "autocomplete": "new-password",
                "placeholder": "Confirm new password",
            }
        )


class MemberPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].widget.attrs.update(
            {
                "autocomplete": "current-password",
                "placeholder": "Current password",
            }
        )
        self.fields["new_password1"].widget.attrs.update(
            {
                "autocomplete": "new-password",
                "placeholder": "New password",
            }
        )
        self.fields["new_password2"].widget.attrs.update(
            {
                "autocomplete": "new-password",
                "placeholder": "Confirm new password",
            }
        )
