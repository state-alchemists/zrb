"""Shared resolution of static items plus factory-produced ones.

`LLMTask`, `LLMChatTask`, and `SubAgentManager` each hold a list of static
tools/toolsets and a list of factories that produce more from a runtime
context. This helper combines them, flattening factory results that return a
list. Kept dependency-free (stdlib only) so any of those modules can import it
without risking an import cycle.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def resolve_factory_items(
    static_items: Sequence[T],
    factories: Sequence[Callable[[Any], "T | list[T]"]],
    ctx: Any,
) -> list[T]:
    """Combine static items with factory output, flattening list-returning factories."""
    resolved: list[T] = list(static_items)
    for factory in factories:
        produced = factory(ctx)
        if isinstance(produced, list):
            resolved.extend(produced)
        else:
            resolved.append(produced)
    return resolved
