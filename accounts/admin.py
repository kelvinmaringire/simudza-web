from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Additional info", {"fields": ("phone_number",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Additional info", {"fields": ("phone_number",)}),
    )
    list_display = ("username", "email", "first_name", "last_name", "phone_number", "is_staff")
