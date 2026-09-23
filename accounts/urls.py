from django.urls import path

from .views import (
    DashboardView,
    MemberLoginView,
    MemberLogoutView,
    MemberPasswordChangeDoneView,
    MemberPasswordChangeView,
    MemberPasswordResetCompleteView,
    MemberPasswordResetConfirmView,
    MemberPasswordResetDoneView,
    MemberPasswordResetView,
    MemberSignUpView,
)

app_name = "accounts"

urlpatterns = [
    path("sign-in/", MemberLoginView.as_view(), name="login"),
    path("sign-up/", MemberSignUpView.as_view(), name="signup"),
    path("sign-out/", MemberLogoutView.as_view(), name="logout"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path(
        "password-reset/",
        MemberPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        MemberPasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        MemberPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        MemberPasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path(
        "password-change/",
        MemberPasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "password-change/done/",
        MemberPasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
]
