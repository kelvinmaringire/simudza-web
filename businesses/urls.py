from django.urls import path

from .views import (
    BusinessDetailView,
    BusinessListView,
    BusinessResultsView,
    CompanySubmitView,
    ProductSubmitView,
    RetailLocationSubmitView,
    SubmissionHubView,
)

app_name = "businesses"

urlpatterns = [
    path("", BusinessListView.as_view(), name="index"),
    path("results/", BusinessResultsView.as_view(), name="results"),
    path("submit/", SubmissionHubView.as_view(), name="submit"),
    path("submit/company/", CompanySubmitView.as_view(), name="submit_company"),
    path("submit/product/", ProductSubmitView.as_view(), name="submit_product"),
    path(
        "submit/product/<int:product_id>/",
        ProductSubmitView.as_view(),
        name="submit_product_update",
    ),
    path(
        "submit/location/",
        RetailLocationSubmitView.as_view(),
        name="submit_location",
    ),
    path("<slug:slug>/", BusinessDetailView.as_view(), name="detail"),
]
