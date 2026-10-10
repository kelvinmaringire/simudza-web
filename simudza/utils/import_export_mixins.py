"""Shared django-import-export hooks for registry models."""

from __future__ import annotations

from businesses.verification.levels import LifecycleStatus, VerificationLevel


class VerificationLevelMixin:
    def before_save_instance(self, instance, row, **kwargs):
        super().before_save_instance(instance, row, **kwargs)
        self.validate_verification_level(instance, user=kwargs.get("user"))
        self.validate_lifecycle_status(instance)

    def validate_verification_level(self, instance, *, user=None):
        from businesses.verification.workflow import level_change_error

        level = getattr(instance, "verification_level", "") or ""
        if level and level not in VerificationLevel.values:
            raise ValueError(f"Invalid verification_level: {level}")
        if not level:
            return
        old_level = None
        if instance.pk:
            old_level = (
                type(instance)
                .objects.filter(pk=instance.pk)
                .values_list("verification_level", flat=True)
                .first()
            )
        error = level_change_error(user, old_level, level)
        if error:
            raise ValueError(error)

    def validate_lifecycle_status(self, instance):
        status = getattr(instance, "lifecycle_status", "") or ""
        if status and status not in LifecycleStatus.values:
            raise ValueError(f"Invalid lifecycle_status: {status}")


class ImportUserMixin:
    """Track importing user on resources that support verified_by."""

    def before_save_instance(self, instance, row, **kwargs):
        super().before_save_instance(instance, row, **kwargs)
        user = kwargs.get("user")
        if user and hasattr(instance, "verified_by") and row.get("verified_at"):
            instance.verified_by = user
