import django_filters
from django.db.models import Q

from businesses.models import Business
from categories.models import Category
from products.models import Product

from .models import DirectoryListing


def _directory_base_qs():
    return DirectoryListing.objects.filter(
        show_in_directory=True,
        product__status=Product.ProductStatus.PUBLISHED,
    )


def _category_descendant_ids(category):
    """Return category pk plus all active descendants at any depth."""
    ids = {category.pk}
    stack = [category.pk]
    while stack:
        parent_id = stack.pop()
        child_ids = Category.objects.filter(
            parent_id=parent_id,
            is_active=True,
        ).values_list("pk", flat=True)
        for child_id in child_ids:
            if child_id not in ids:
                ids.add(child_id)
                stack.append(child_id)
    return ids


def build_directory_category_tree(selected_id=None):
    """
    Recursive category tree for the directory filter.

    Includes every active category that either has a listed product or is an
    ancestor of one, so intermediate levels stay visible. Nodes start collapsed
    unless the current selection is this node or a descendant.
    """
    try:
        selected_id = int(selected_id) if selected_id not in (None, "") else None
    except (TypeError, ValueError):
        selected_id = None

    listed_ids = set(
        _directory_base_qs().values_list("product__category_id", flat=True)
    )
    if not listed_ids:
        return []

    all_categories = {
        category.pk: category
        for category in Category.objects.filter(is_active=True).only(
            "pk",
            "name",
            "parent_id",
            "sort_order",
        )
    }

    visible_ids = set()
    for category_id in listed_ids:
        current_id = category_id
        while current_id and current_id in all_categories:
            if current_id in visible_ids:
                break
            visible_ids.add(current_id)
            current_id = all_categories[current_id].parent_id

    selected_path = set()
    if selected_id and selected_id in all_categories:
        current_id = selected_id
        while current_id and current_id in all_categories:
            selected_path.add(current_id)
            current_id = all_categories[current_id].parent_id

    children_map = {}
    for category_id in visible_ids:
        category = all_categories[category_id]
        parent_id = category.parent_id
        if parent_id in visible_ids:
            children_map.setdefault(parent_id, []).append(category)
        else:
            children_map.setdefault(None, []).append(category)

    def sort_key(category):
        has_children = bool(children_map.get(category.pk))
        # Branches first, then existing sort_order + alphabetical order.
        return (0 if has_children else 1, category.sort_order, category.name.lower())

    for parent_id in children_map:
        children_map[parent_id].sort(key=sort_key)

    def build_node(category, depth):
        child_nodes = [
            build_node(child, depth + 1)
            for child in children_map.get(category.pk, [])
        ]
        selected = category.pk == selected_id
        expanded = bool(child_nodes) and (
            selected
            or any(child["selected"] or child["expanded"] for child in child_nodes)
            or category.pk in selected_path
        )
        return {
            "category": category,
            "children": child_nodes,
            "expanded": expanded,
            "selected": selected,
            "depth": depth,
        }

    return [
        build_node(category, 0)
        for category in children_map.get(None, [])
    ]


class DirectoryListingFilter(django_filters.FilterSet):
    """Public directory facets mapped to Product / Business / Inventory fields."""

    q = django_filters.CharFilter(method="filter_q", label="Search")

    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.filter(is_active=True),
        method="filter_category",
        label="Category",
    )

    town_or_city = django_filters.ChoiceFilter(
        field_name="product__business__town_or_city",
        lookup_expr="iexact",
        empty_label=None,
        label="Town / city",
    )

    origin_type = django_filters.ChoiceFilter(
        field_name="product__origin_type",
        choices=Product.OriginType.choices,
        empty_label="All product types",
        label="Product type",
    )

    verified = django_filters.BooleanFilter(
        method="filter_verified",
        label="Verified only",
    )

    class Meta:
        model = DirectoryListing
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        listed = _directory_base_qs()

        towns = (
            listed.exclude(product__business__town_or_city="")
            .values_list("product__business__town_or_city", flat=True)
            .distinct()
            .order_by("product__business__town_or_city")
        )
        self.filters["town_or_city"].field.choices = [
            ("", "All towns / cities"),
            *[(town, town) for town in towns],
        ]

    def filter_q(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(product__name__icontains=value)
            | Q(product__brand_name__icontains=value)
            | Q(product__short_description__icontains=value)
            | Q(product__description__icontains=value)
            | Q(product__sku__icontains=value)
            | Q(product__business__name__icontains=value)
            | Q(product__category__name__icontains=value)
        ).distinct()

    def filter_category(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            product__category_id__in=_category_descendant_ids(value)
        )

    def filter_verified(self, queryset, name, value):
        if value is True:
            return queryset.filter(
                product__business__verification_status=(
                    Business.VerificationStatus.VERIFIED
                )
            )
        return queryset
