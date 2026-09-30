from django.urls import path

from .views import ReportBusinessView, ReportProductView

app_name = "reviews"

urlpatterns = [
    path(
        "report/product/<slug:slug>/",
        ReportProductView.as_view(),
        name="report_product",
    ),
    path(
        "report/business/<slug:slug>/",
        ReportBusinessView.as_view(),
        name="report_business",
    ),
]
