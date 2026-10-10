"""`scoped()`: a `ContextVar` set/reset pair on `try`/`finally`, so a scoped
bind cannot leak past its block."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TypeVar

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
