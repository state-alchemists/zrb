"""The shared, ordered prompt middlewares every ``PromptManager`` appends after its built-in sections.

Each layer (registry, manager) replays its own append/prepend/remove ops over
a freshly resolved base whenever the effective list is read.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

from zrb.config.config import CFG

#: The concrete prompt middleware list.
PromptList: TypeAlias = list[Any]

#: A prompt set supplier: a concrete middleware list, a zero-arg callable
#: returning one (resolved at query time), or ``None`` meaning "no prompts
#: set" (the code default).
PromptSetValue: TypeAlias = PromptList | Callable[[], PromptList] | None


class PromptDelta:
    """Ordered append/prepend/remove ops replayed over a base list."""

    def __init__(self) -> None:
        self._ops: list[tuple[str, tuple[Any, ...]]] = []

    def append(self, *middleware: Any) -> None:
        self._ops.append(("append", middleware))

    def prepend(self, *middleware: Any) -> None:
        self._ops.append(("prepend", middleware))

    def remove(self, middleware: Any) -> None:
        self._ops.append(("remove", (middleware,)))

    def clear(self) -> None:
        self._ops.clear()

    def apply(self, base: PromptList) -> PromptList:
        resolved = list(base)
        for kind, payload in self._ops:
            if kind == "append":
                resolved.extend(payload)
            elif kind == "prepend":
                resolved[0:0] = payload
            else:
                mw = payload[0]
                for i, existing in enumerate(resolved):
                    if existing is mw or existing == mw:
                        del resolved[i]
                        break
        return resolved


class PromptRegistry:
    """The shared default prompts emitted after the built-in sections.

    The base is the ``set_prompts`` value, else ``default``; either may be a
    zero-argument callable resolved at query time. Delta ops are replayed over
    it on every read. ``remove_prompt`` matches by identity.
    """

    def __init__(self, default: PromptSetValue = None) -> None:
        """default: a middleware list, or a zero-argument callable returning one."""
        self._default: PromptSetValue = default
        self._prompts: PromptSetValue = None
        self._deltas = PromptDelta()

    def _resolve(self, value: PromptSetValue) -> PromptList:
        if callable(value):
            value = value()
        if value is None:
            return []
        return list(value)

    def get_prompts(self) -> PromptList:
        """The resolved prompts, with delta ops applied over the current base."""
        base = self._prompts if self._prompts is not None else self._default
        return self._deltas.apply(self._resolve(base))

    def set_prompts(self, value: PromptSetValue) -> None:
        """Replace the base wholesale (list or deferred callable) and clear delta ops."""
        self._prompts = value
        self._deltas.clear()

    def append_prompt(self, *middleware: Any) -> None:
        """Append *middleware* after the current defaults."""
        self._deltas.append(*middleware)

    def prepend_prompt(self, *middleware: Any) -> None:
        """Prepend *middleware* before the current defaults (runs first)."""
        self._deltas.prepend(*middleware)

    def remove_prompt(self, middleware: Any) -> None:
        """Drop the first occurrence of the exact *middleware* value."""
        self._deltas.remove(middleware)

    def clear(self) -> None:
        """Return to the seeded default, dropping explicit prompts and delta ops."""
        self._prompts = None
        self._deltas.clear()


def _cfg_prompt_default() -> PromptList:
    """The env-var twin of ``prompt_registry``, read lazily."""
    return list(CFG.LLM_PROMPT)


#: The registry every ``PromptManager()`` reads; defaults to ``CFG.LLM_PROMPT``, read lazily.
prompt_registry = PromptRegistry(default=_cfg_prompt_default)
