"""Live data-quality checks for categories (no stored score)."""

from __future__ import annotations

from django.db.models import Count, Q

from products.models import Product

from .models import Category

ISSUE_LABELS = {
    "missing_description": "Missing description",
    "inactive_with_products": "Inactive but has products",
    "no_published_products": "No published products",
}


def _annotated_qs():
    return Category.objects.annotate(
        published_count=Count(
            "products",
            filter=Q(products__status=Product.ProductStatus.PUBLISHED),
        ),
        product_count=Count("products"),
    )


def category_issues(category: Category) -> list[str]:
    if not category.description or not category.description.strip():
        missing_desc = True
    else:
        missing_desc = False

    published_count = Product.objects.filter(
        category=category,
        status=Product.ProductStatus.PUBLISHED,
    ).count()
    product_count = Product.objects.filter(category=category).count()

    issues = []
    if missing_desc:
        issues.append("missing_description")
    if not category.is_active and product_count > 0:
        issues.append("inactive_with_products")
    if published_count == 0:
        issues.append("no_published_products")
    return issues


def category_issue_labels(category: Category) -> list[str]:
    return [ISSUE_LABELS[code] for code in category_issues(category)]


def issue_counts():
    qs = _annotated_qs()
    return {
        "missing_description": qs.filter(description="").count(),
        "inactive_with_products": qs.filter(
            is_active=False, product_count__gt=0
        ).count(),
        "no_published_products": qs.filter(published_count=0).count(),
    }


def needing_attention_count():
    return Category.objects.needing_attention().count()
