from django.urls import path

from .views import (
    BusinessDetailView,
    BusinessListView,
    BusinessResultsView,
    CompanySubmitView,
    ProductSubmitView,
    SubmissionHubView,
)

app_name = "businesses"

urlpatterns = [
    path("", BusinessListView.as_view(), name="index"),
    path("results/", BusinessResultsView.as_view(), name="results"),
    path("submit/", SubmissionHubView.as_view(), name="submit"),
    path("submit/company/", CompanySubmitView.as_view(), name="submit_company"),
    path(
        "submit/company/<int:pk>/",
        CompanySubmitView.as_view(),
        name="submit_company_update",
    ),
    path("submit/product/", ProductSubmitView.as_view(), name="submit_product"),
    path(
        "submit/product/<int:product_id>/",
        ProductSubmitView.as_view(),
        name="submit_product_update",
    ),
    path("<slug:slug>/", BusinessDetailView.as_view(), name="detail"),
]
