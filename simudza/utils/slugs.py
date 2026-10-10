from django.db import IntegrityError, transaction
from django.utils.text import slugify

MAX_SLUG_ATTEMPTS = 10


def unique_slug(model, name, *, fallback, exclude_pk=None, field="slug"):
    """Best-effort free slug (name, name-2, ...). Not a guarantee under concurrency."""
    base = slugify(name) or fallback
    max_length = model._meta.get_field(field).max_length
    if max_length:
        base = base[: max_length - 6].rstrip("-") or fallback
    queryset = model._default_manager.all()
    if exclude_pk:
        queryset = queryset.exclude(pk=exclude_pk)
    candidate = base
    suffix = 2
    while queryset.filter(**{field: candidate}).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def save_with_unique_slug(instance, name, *, fallback, save=None, field="slug"):
    """
    Assign a slug from ``name`` and save, retrying with the next free slug when a
    concurrent writer claims it first. The unique constraint is the real guard;
    any other IntegrityError is re-raised.
    """
    model = type(instance)
    save = save or instance.save
    for attempt in range(MAX_SLUG_ATTEMPTS):
        setattr(
            instance,
            field,
            unique_slug(model, name, fallback=fallback, exclude_pk=instance.pk, field=field),
        )
        try:
            with transaction.atomic():
                save()
            return instance
        except IntegrityError:
            taken = (
                model._default_manager.filter(**{field: getattr(instance, field)})
                .exclude(pk=instance.pk)
                .exists()
            )
            if not taken or attempt == MAX_SLUG_ATTEMPTS - 1:
                raise
    return instance
