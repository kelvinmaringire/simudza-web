"""Live data-quality checks for categories (no stored score)."""

from __future__ import annotations

from .models import ATTENTION_ISSUES, Category, issue_flag

ISSUE_LABELS = {
    "inactive_with_products": "Inactive but has products",
    "no_published_products": "No published products",
}


def category_issues(category: Category) -> list[str]:
    """Issue codes for one category; reuses ``with_attention()`` flags when already loaded."""
    flags = [issue_flag(code) for code in ATTENTION_ISSUES]
    if all(hasattr(category, flag) for flag in flags):
        values = {flag: getattr(category, flag) for flag in flags}
    else:
        values = (
            Category.objects.filter(pk=category.pk)
            .with_attention()
            .values(*flags)
            .first()
        ) or {}
    return [code for code in ATTENTION_ISSUES if values.get(issue_flag(code))]


def category_issue_labels(category: Category) -> list[str]:
    return [ISSUE_LABELS[code] for code in category_issues(category)]


def issue_counts():
    return {
        code: Category.objects.with_issue(code).count()
        for code in ATTENTION_ISSUES
    }


def needing_attention_count():
    return Category.objects.needing_attention().count()
