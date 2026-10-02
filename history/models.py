import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class ChangeLogQuerySet(models.QuerySet):
    def for_object(self, obj):
        ct = ContentType.objects.get_for_model(obj, for_concrete_model=False)
        return self.filter(content_type=ct, object_id=str(obj.pk))

    def for_model(self, model):
        ct = ContentType.objects.get_for_model(model, for_concrete_model=False)
        return self.filter(content_type=ct)


class ChangeLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        DELETED = "deleted", "Deleted"

    class Source(models.TextChoices):
        ADMIN = "admin", "Admin"
        DASHBOARD = "dashboard", "Dashboard"
        SUBMISSION = "submission", "Submission"
        IMPORT = "import", "Import"
        SYSTEM = "system", "System"
        WEB = "web", "Web"
        BULK_EDIT = "bulk_edit", "Bulk edit"

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="change_logs",
    )
    object_id = models.CharField(max_length=64, db_index=True)
    content_object = GenericForeignKey("content_type", "object_id")

    object_repr = models.CharField(max_length=300)

    action = models.CharField(max_length=20, choices=Action.choices, db_index=True)

    field_name = models.CharField(max_length=100, blank=True)
    field_label = models.CharField(max_length=200, blank=True)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="change_logs",
    )
    changed_by_repr = models.CharField(max_length=150, blank=True)

    changed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reason = models.CharField(max_length=500, blank=True)
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.WEB,
        db_index=True,
    )

    batch_id = models.UUIDField(default=uuid.uuid4, db_index=True)

    objects = ChangeLogQuerySet.as_manager()

    class Meta:
        ordering = ["-changed_at", "-pk"]
        indexes = [
            models.Index(
                fields=["content_type", "object_id", "-changed_at"],
                name="history_changelog_obj_time",
            ),
        ]
        verbose_name = "change log entry"
        verbose_name_plural = "change log"

    def __str__(self):
        if self.field_name:
            return f"{self.object_repr}: {self.field_label or self.field_name}"
        return self.object_repr
