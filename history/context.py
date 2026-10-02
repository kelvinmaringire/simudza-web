from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class HistoryContext:
    user: object | None = None
    source: str | None = None
    reason: str = ""


_history_context: ContextVar[HistoryContext | None] = ContextVar(
    "history_context",
    default=None,
)


def current_context() -> HistoryContext:
    ctx = _history_context.get()
    if ctx is None:
        return HistoryContext()
    return ctx


@contextmanager
def change_context(*, user=None, source=None, reason=None):
    parent = current_context()
    merged = replace(
        parent,
        user=user if user is not None else parent.user,
        source=source if source is not None else parent.source,
        reason=reason if reason is not None else parent.reason,
    )
    token = _history_context.set(merged)
    try:
        yield merged
    finally:
        _history_context.reset(token)
