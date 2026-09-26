from django.shortcuts import redirect
from django.urls import path

from .views import ProductDetailView

app_name = "products"


def products_index_redirect(request):
    """Product browsing lives in the directory."""
    return redirect("directory:index", permanent=False)


urlpatterns = [
    path("", products_index_redirect, name="index"),
    path("<slug:slug>/", ProductDetailView.as_view(), name="detail"),
]
