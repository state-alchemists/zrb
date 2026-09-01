"""The canonical collection of extra prompt middlewares.

Split out of ``PromptManager``: ``PromptRegistry`` owns the
shared default prompts (the ordered middleware list emitted after every
built-in section), while ``PromptManager`` stays a per-task resolved view
that pulls its default from ``prompt_registry`` unless the caller passes
``prompts`` explicitly.

Prompts are an *ordered* middleware pipeline (order is the semantics), so
the mutation verbs are ``append_prompt`` / ``prepend_prompt``. The default
may also be a *deferred* provider — a zero-argument callable returning the
prompt list — resolved at query time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, TypeAlias

from zrb.config.config import CFG

if TYPE_CHECKING:
    from .manager import PromptMiddleware

#: The concrete prompt middleware list.
PromptList: TypeAlias = list["PromptMiddleware | str"]

#: A prompt set supplier: a concrete middleware list, a zero-arg callable
#: returning one (resolved at query time), or ``None`` meaning "no prompts
#: set" (the code default).
PromptSetValue: TypeAlias = PromptList | Callable[[], PromptList] | None


class PromptRegistry:
    """The shared default prompts emitted after the built-in sections.

    ``PromptManager(prompts=None)`` reads its appended prompts from the
    default registry (``prompt_registry``); the registry default is empty
    until something ``set_prompts``/``append_prompt``/``prepend_prompt``
    into it. Item identity is the key — ``remove_prompt`` drops the exact
    middleware value handed to ``set_prompts`` / ``append_prompt``.

    The default itself may be *deferred*: ``default`` (constructor genomic
    argument) — and ``set_prompts`` — accept a zero-argument callable that
    resolves at query time. The module singleton's default
    is a lazy ``CFG.LLM_PROMPT`` read, so env vars keep working without the
    registry copying them at startup.
    """

    def __init__(self, default: PromptSetValue = None) -> None:
        """Create an empty registry.

        default: the seeded prompt list — a concrete middleware list or a
        zero-argument callable resolved at query time (deferred).
        """
        self._default: PromptSetValue = default
        self._prompts: PromptSetValue = None

    def _resolve(self, value: PromptSetValue) -> PromptList:
        """Resolve a stored prompt value to a concrete list."""
        if callable(value):
            value = value()
        if value is None:
            return []
        return list(value)

    def get_prompts(self) -> PromptList:
        """The resolved default prompts, in registration order.

        Explicit mutations win; absent any, the seeded ``default`` (which may
        itself be deferred) is resolved, backstopped by the empty list.
        """
        if self._prompts is not None:
            return self._resolve(self._prompts)
        return self._resolve(self._default)

    def set_prompts(self, value: PromptSetValue) -> None:
        """Replace the default prompts wholesale.

        *value* may be a concrete list or a zero-arg callable resolving to
        one; a callable is evaluated lazily at each ``get_prompts`` (and any
        subsequent mutation) rather than at set time.
        """
        self._prompts = value

    def append_prompt(self, *middleware: "PromptMiddleware | str") -> None:
        """Append *middleware* after the current defaults.

        Freezes a deferred provider into a concrete list first, so the
        appended entries become part of the resolved default.
        """
        resolved = self.get_prompts()
        resolved.extend(middleware)
        self._prompts = resolved

    def prepend_prompt(self, *middleware: "PromptMiddleware | str") -> None:
        """Prepend *middleware* before the current defaults (runs first)."""
        resolved = self.get_prompts()
        resolved[0:0] = middleware
        self._prompts = resolved

    def remove_prompt(self, middleware: "PromptMiddleware | str") -> None:
        """Drop the first occurrence of the exact *middleware* value.

        Removal is by identity — the caller names the very value it
        ``add``-ed, as the other registries' ``remove_<name>`` do for name-
        keyed entries.
        """
        resolved = self.get_prompts()
        for i, existing in enumerate(resolved):
            if existing is middleware or existing == middleware:
                del resolved[i]
                break
        self._prompts = resolved

    def clear(self) -> None:
        """Drop explicit prompts, returning to the seeded default."""
        self._prompts = None


def _cfg_prompt_default() -> PromptList:
    """The env-var twin of ``prompt_registry``, read lazily."""
    return list(CFG.LLM_PROMPT)


#: The shared default prompt registry every ``PromptManager()`` reads. Its
#: default resolves ``CFG.LLM_PROMPT`` lazily, so env vars configure prompts
#: without any startup copy.
prompt_registry = PromptRegistry(default=_cfg_prompt_default)
