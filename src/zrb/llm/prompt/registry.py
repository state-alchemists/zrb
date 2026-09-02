"""The canonical collection of extra prompt middlewares.

Split out of ``PromptManager``: ``PromptRegistry`` owns the
shared default prompts (the ordered middleware list emitted after every
built-in section), while ``PromptManager`` stays a per-task resolved view
that pulls its default from ``prompt_registry`` unless the caller passes
``prompts`` explicitly.

Prompts are an *ordered* middleware pipeline (order is the semantics), so
the mutation verbs are ``append_prompt`` / ``prepend_prompt``. Each layer
(registry, manager) keeps its own ordered delta ops (append/prepend/remove)
and replays them over its freshly-resolved base whenever the effective list
is read. The default may also be a *deferred* provider — a zero-argument
callable returning the prompt list — resolved at query time.
"""

from __future__ import annotations

from typing import Any, Callable, TypeAlias

from zrb.config.config import CFG

#: The concrete prompt middleware list.
PromptList: TypeAlias = list[Any]

#: A prompt set supplier: a concrete middleware list, a zero-arg callable
#: returning one (resolved at query time), or ``None`` meaning "no prompts
#: set" (the code default).
PromptSetValue: TypeAlias = PromptList | Callable[[], PromptList] | None


class PromptDelta:
    """Ordered append/prepend/remove ops replayed over a base list.

    Shared by ``PromptRegistry`` and ``PromptManager``: each layer keeps
    its own delta ops and applies them over its freshly-resolved base
    (its own explicit value, else the layer below) whenever the effective
    prompts are read.
    """

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

    ``PromptManager(prompts=None)`` reads its appended prompts from the
    default registry (``prompt_registry``); the registry default is empty
    until something ``set_prompts``/``append_prompt``/``prepend_prompt``
    into it. Item identity is the key — ``remove_prompt`` drops the exact
    middleware value handed to ``set_prompts`` / ``append_prompt``.

    The layering model (ADR-0090): each registry keeps a ``_default``
    fallback (possibly callable/deferred) and an explicit ``_prompts``
    value set by ``set_prompts``. Delta ops (append/prepend/remove) are
    stored as ``PromptDelta`` ops and replayed over the resolved base
    (explicit value if set, else the default) at query time.

    ``set_prompts`` replaces the layer's own value wholesale and clears
    all delta ops. ``append_prompt`` / ``prepend_prompt`` /
    ``remove_prompt`` layer ops on top of the current base.

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
        self._deltas = PromptDelta()

    def _resolve(self, value: PromptSetValue) -> PromptList:
        """Resolve a stored prompt value to a concrete list."""
        if callable(value):
            value = value()
        if value is None:
            return []
        return list(value)

    def get_prompts(self) -> PromptList:
        """The resolved default prompts, in registration order.

        The base is the explicit ``_prompts`` value if set (via
        ``set_prompts``), otherwise the seeded ``_default``. Delta ops
        (append/prepend/remove) are applied live over the resolved base
        each time this is called, so later changes to the default (e.g.
        env-var edits) are picked up without an explicit re-set.
        """
        base = self._prompts if self._prompts is not None else self._default
        return self._deltas.apply(self._resolve(base))

    def set_prompts(self, value: PromptSetValue) -> None:
        """Replace the default prompts wholesale.

        *value* may be a concrete list or a zero-arg callable resolving to
        one; a callable is evaluated lazily at each ``get_prompts`` rather
        than at set time. Clears all pending delta ops.
        """
        self._prompts = value
        self._deltas.clear()

    def append_prompt(self, *middleware: Any) -> None:
        """Append *middleware* after the current defaults.

        The op is stored and replayed over the resolved base on every
        ``get_prompts`` call, so later changes to the default layer (env,
        ``set_prompts``) stay visible.
        """
        self._deltas.append(*middleware)

    def prepend_prompt(self, *middleware: Any) -> None:
        """Prepend *middleware* before the current defaults (runs first)."""
        self._deltas.prepend(*middleware)

    def remove_prompt(self, middleware: Any) -> None:
        """Drop the first occurrence of the exact *middleware* value.

        Removal is by identity — the caller names the very value it
        ``add``-ed, as the other registries' ``remove_<name>`` do for name-
        keyed entries.
        """
        self._deltas.remove(middleware)

    def clear(self) -> None:
        """Drop explicit prompts and all delta ops, returning to the seeded
        default."""
        self._prompts = None
        self._deltas.clear()


def _cfg_prompt_default() -> PromptList:
    """The env-var twin of ``prompt_registry``, read lazily."""
    return list(CFG.LLM_PROMPT)


#: The shared default prompt registry every ``PromptManager()`` reads. Its
#: default resolves ``CFG.LLM_PROMPT`` lazily, so env vars configure prompts
#: without any startup copy.
prompt_registry = PromptRegistry(default=_cfg_prompt_default)
