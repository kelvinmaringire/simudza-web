from django.urls import path

from .views import (
    DirectoryIndexView,
    DirectoryProductDetailView,
    DirectoryResultsView,
)

app_name = "directory"

urlpatterns = [
    path("", DirectoryIndexView.as_view(), name="index"),
    path("results/", DirectoryResultsView.as_view(), name="results"),
    path("<slug:slug>/", DirectoryProductDetailView.as_view(), name="product"),
]
