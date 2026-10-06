from django.db import models
from django.db.models import Count, Q
from django.urls import reverse


# Data-quality issues, evaluated on ``with_product_counts()``. Top-level
# categories organise the taxonomy and need not hold products directly.
ATTENTION_ISSUES = {
    "inactive_with_products": Q(is_active=False, product_count__gt=0),
    "no_published_products": Q(parent__isnull=False, published_count=0),
}


class CategoryQuerySet(models.QuerySet):
    def with_product_counts(self):
        from products.models import Product

        return self.annotate(
            published_count=Count(
                "products",
                filter=Q(products__status=Product.ProductStatus.PUBLISHED),
            ),
            product_count=Count("products"),
        )

    def with_issue(self, code):
        return self.with_product_counts().filter(ATTENTION_ISSUES[code])

    def needing_attention(self):
        conditions = Q()
        for condition in ATTENTION_ISSUES.values():
            conditions |= condition
        return self.with_product_counts().filter(conditions)

    def with_tree_path(self):
        """Annotate ``tree_path_ids`` / ``tree_path_names`` (root → self)."""
        from .hierarchy import tree_path_expression

        table = self.model._meta.db_table
        return self.annotate(
            tree_path_ids=tree_path_expression(table, "ids"),
            tree_path_names=tree_path_expression(table, "names"),
        )


class Category(models.Model):
    name = models.CharField(max_length=150)

    slug = models.SlugField(
        max_length=180,
        unique=True,
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="children",
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    objects = CategoryQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        verbose_name = "category"
        verbose_name_plural = "categories"

    def __str__(self):
        from .hierarchy import iter_ancestors

        names = [a.name for a in iter_ancestors(self)][::-1]
        return " → ".join([*names, self.name])

    def clean(self):
        from .hierarchy import validate_parent

        super().clean()
        validate_parent(self, self.parent)

    def get_absolute_url(self):
        return reverse(
            "categories:detail",
            kwargs={"slug": self.slug},
        )
