"""`HookRegistry` — the canonical collection of lifecycle hooks.

Per ADR-0090, a registry is the *source of defaults*: it stores the full set of
hooks found by filesystem discovery *plus* everything registered in code, and
answers queries. It does not scan the filesystem or run hooks — that is
`HookManager`'s job.

Unlike skills/agents, hooks are **event-keyed accumulations**, not a name-keyed
replacement surface: many sources co-register onto the same event, and hooks are
never wholesale-replaced by a scan. So this registry's mutations are
append/remove oriented (`register`, `remove_hook`, `remove_event_hooks`), with
`set_hooks` available for a deliberate clean-slate swap of one event.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, overload

from zrb.config.config import CFG

if TYPE_CHECKING:
    from zrb.llm.hook.interface import HookCallable

from zrb.llm.hook.schema import HookConfig
from zrb.llm.hook.types import HookEvent


class HookRegistry:
    """The canonical collection of registered hooks.

    Owns the event→hooks map (`_hooks`), the global hook list (`_global_hooks`),
    and the bookkeeping maps a manager needs to resolve a hook's config by
    identity (`_hook_to_config`) and to surface configs for debugging
    (`_hook_configs`). A manager composes this and delegates every read or write.
    """

    def __init__(self):
        self._hooks: dict[HookEvent, list[HookCallable]] = defaultdict(list)
        self._global_hooks: list[HookCallable] = []
        self._hook_configs: dict[str, HookConfig] = {}
        self._hook_to_config: dict[HookCallable, HookConfig] = {}

    # --- Registration ------------------------------------------------------

    def register(
        self,
        hook: HookCallable,
        events: list[HookEvent] | None = None,
        config: HookConfig | None = None,
    ) -> None:
        """Register *hook*, optionally with its *events* and *config*.

        An empty/`None` *events* makes it a global hook (runs on every event);
        otherwise it is registered for each named event. *config* is kept for
        priority sorting and timeout lookup, keyed by hook identity.
        """
        if config:
            self._hook_to_config[hook] = config

        if not events:
            self._global_hooks.append(hook)
        else:
            for event in events:
                self._hooks[event].append(hook)

    def remove_hook(self, hook: HookCallable) -> None:
        """Drop *hook* from every event and the global list."""
        for event in list(self._hooks):
            self._hooks[event] = [h for h in self._hooks[event] if h is not hook]
        self._global_hooks = [h for h in self._global_hooks if h is not hook]
        self._hook_to_config.pop(hook, None)

    def remove_event_hooks(self, event: HookEvent) -> None:
        """Drop every hook registered for *event* (global hooks untouched)."""
        self._hooks.pop(event, None)

    def set_hooks(
        self,
        event: HookEvent,
        hooks: list[HookCallable],
        configs: dict[HookCallable, HookConfig] | None = None,
    ) -> None:
        """Replace the hook list for *event* — a deliberate clean-slate swap.

        *configs* maps each hook to its `HookConfig`, repopulating
        `_hook_to_config` for the new set.
        """
        self._hooks[event] = list(hooks)
        if configs:
            self._hook_to_config.update(configs)

    def clear_manual(self) -> None:
        """Drop the entire collection. Used by a reload to restart from scan."""
        self._hooks = defaultdict(list)
        self._global_hooks = []
        self._hook_configs = {}
        self._hook_to_config = {}

    def record_config(self, name: str, config: HookConfig) -> None:
        """Remember *config* by *name* for debugging (e.g. when hydrating)."""
        self._hook_configs[name] = config

    # --- Queries -----------------------------------------------------------

    def get_hooks(self, event: HookEvent) -> list[HookCallable]:
        """All hooks registered for *event*, filtered by the ``LLM_HOOKS``
        name allowlist twin (ADR-0091): non-empty ``CFG.LLM_HOOKS`` keeps only
        the named hooks."""
        return self._filter(self._hooks[event])

    def get_global_hooks(self) -> list[HookCallable]:
        """All global hooks (run on every event), filtered by the ``LLM_HOOKS``
        name allowlist twin when it is set."""
        return self._filter(self._global_hooks)

    def _filter(self, hooks: list[HookCallable]) -> list[HookCallable]:
        """Drop hooks hidden by the ``LLM_HOOKS`` allowlist (read lazily)."""
        allowed = list(CFG.LLM_HOOKS or [])
        if not allowed:
            return list(hooks)
        return [h for h in hooks if self._hook_name(h) in allowed]

    def _hook_name(self, hook: HookCallable) -> str:
        """Dispatch name for *hook*: config name when hydrated, else the
        callable's own ``__name__``/``name``."""
        config = self._hook_to_config.get(hook)
        if config is not None:
            return config.name
        return getattr(hook, "__name__", "") or getattr(hook, "name", "") or ""

    @overload
    def get_hook_config(
        self, hook: HookCallable, default: HookConfig
    ) -> HookConfig: ...

    @overload
    def get_hook_config(
        self, hook: HookCallable, default: HookConfig | None = None
    ) -> HookConfig | None: ...

    def get_hook_config(
        self, hook: HookCallable, default: HookConfig | None = None
    ) -> HookConfig | None:
        """The `HookConfig` registered for *hook*, or *default* when absent."""
        return self._hook_to_config.get(hook, default)

    def get_configs(self) -> dict[str, HookConfig]:
        """All registered configs by hook name, for debugging."""
        return dict(self._hook_configs)


hook_registry = HookRegistry()
