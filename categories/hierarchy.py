"""Category tree rules: parent validation and safe ancestor walks."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db.models.expressions import RawSQL

# Root-first path for the outer row; the ANY() guard stops on saved cycles.
_TREE_PATH_SQL = """(
    WITH RECURSIVE anc(id, parent_id, ids, names) AS (
        SELECT c.id, c.parent_id, ARRAY[c.id], ARRAY[c.name::text]
        FROM {table} c
        WHERE c.id = {table}.id
        UNION ALL
        SELECT p.id, p.parent_id, p.id || anc.ids, p.name::text || anc.names
        FROM {table} p
        JOIN anc ON p.id = anc.parent_id
        WHERE NOT p.id = ANY(anc.ids)
    )
    SELECT {column} FROM anc ORDER BY cardinality(ids) DESC LIMIT 1
)"""


def tree_path_expression(table: str, column: str) -> RawSQL:
    """``column`` is ``ids`` (int[]) or ``names`` (text[]), root first, self last."""
    return RawSQL(_TREE_PATH_SQL.format(table=table, column=column), [])


def iter_ancestors(category):
    """
    Yield parents from nearest to root.

    Stops at a repeated node so rows already saved with a cycle cannot loop
    forever.
    """
    seen = {category.pk} if category.pk else set()
    current = category.parent
    while current is not None and current.pk not in seen:
        seen.add(current.pk)
        yield current
        current = current.parent


def validate_parent(category, parent) -> None:
    """Raise ValidationError if ``parent`` would make ``category`` self-parented or cyclic."""
    if parent is None or category.pk is None:
        return
    if parent.pk == category.pk:
        raise ValidationError(
            {"parent": "A category cannot be its own parent."},
            code="self_parent",
        )
    if any(ancestor.pk == category.pk for ancestor in iter_ancestors(parent)):
        raise ValidationError(
            {"parent": f"“{parent.name}” is inside “{category.name}”; "
                       "choosing it as parent would create a loop."},
            code="parent_cycle",
        )
