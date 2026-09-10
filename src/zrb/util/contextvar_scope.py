"""The one RAII primitive every scoped `ContextVar` bind in zrb is built from.

A bare `ContextVar.set(value)` with no matching `.reset(token)` leaks: the
value persists past whatever the caller thought was "temporary," including
across unrelated later work sharing the same context, and forever if an
exception skips the (nonexistent) cleanup. `scoped()` is the single place
that pairs set/reset correctly, on a `try`/`finally`, so nothing built on it
can leak this way.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator, TypeVar

T = TypeVar("T")


@contextmanager
def scoped(var: "ContextVar[T]", value: T) -> Generator[None]:
    """Bind `var` to `value` for the `with` block; always reset on exit,
    exception or not."""
    token = var.set(value)
    try:
        yield
    finally:
        var.reset(token)
