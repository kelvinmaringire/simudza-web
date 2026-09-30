"""Shared django-import-export hooks for registry models."""

from __future__ import annotations

from businesses.verification import VerificationLevel


class VerificationLevelMixin:
    def before_save_instance(self, instance, row, **kwargs):
        super().before_save_instance(instance, row, **kwargs)
        self.validate_verification_level(instance)

    def validate_verification_level(self, instance):
        level = getattr(instance, "verification_level", "") or ""
        if level and level not in dict(VerificationLevel.choices):
            raise ValueError(f"Invalid verification_level: {level}")


class ImportUserMixin:
    """Track importing user on resources that support verified_by."""

    def before_save_instance(self, instance, row, **kwargs):
        super().before_save_instance(instance, row, **kwargs)
        user = kwargs.get("user")
        if user and hasattr(instance, "verified_by") and row.get("verified_at"):
            instance.verified_by = user
