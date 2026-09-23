from django.db import models
from django.urls import reverse


class Category(models.Model):
    name = models.CharField(max_length=150)

    slug = models.SlugField(
        max_length=180,
        unique=True,
    )

    description = models.TextField(
        blank=True,
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="children",
    )

    is_active = models.BooleanField(
        default=True,
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "sort_order",
            "name",
        ]

    def __str__(self):
        if self.parent:
            return f"{self.parent} → {self.name}"

        return self.name

    def get_absolute_url(self):
        return reverse(
            "categories:detail",
            kwargs={"slug": self.slug},
        )