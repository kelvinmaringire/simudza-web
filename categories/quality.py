"""Live data-quality checks for categories (no stored score)."""

from __future__ import annotations

from .models import ATTENTION_ISSUES, Category

ISSUE_LABELS = {
    "inactive_with_products": "Inactive but has products",
    "no_published_products": "No published products",
}


def category_issues(category: Category) -> list[str]:
    row = Category.objects.filter(pk=category.pk)
    return [code for code in ATTENTION_ISSUES if row.with_issue(code).exists()]


def category_issue_labels(category: Category) -> list[str]:
    return [ISSUE_LABELS[code] for code in category_issues(category)]


def issue_counts():
    return {
        code: Category.objects.with_issue(code).count()
        for code in ATTENTION_ISSUES
    }


def needing_attention_count():
    return Category.objects.needing_attention().count()
