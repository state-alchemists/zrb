"""`HookRegistry`: the event-keyed collection of lifecycle hooks.

It stores hooks and answers queries; scanning and running them is
`HookManager`'s job.
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
    """The collection of registered hooks and their configs."""

    def __init__(self):
        self._hooks: dict[HookEvent, list[HookCallable]] = defaultdict(list)
        self._global_hooks: list[HookCallable] = []
        self._hook_configs: dict[str, HookConfig] = {}
        self._hook_to_config: dict[HookCallable, HookConfig] = {}

    def add_hook(
        self,
        hook: HookCallable,
        events: list[HookEvent] | None = None,
        config: HookConfig | None = None,
    ) -> None:
        """Register *hook* for *events*, or globally when *events* is empty."""
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
        self._prune_hook_configs()

    def set_hooks(
        self,
        event: HookEvent,
        hooks: list[HookCallable],
        configs: dict[HookCallable, HookConfig] | None = None,
    ) -> None:
        """Replace the hook list for *event*; configs of unregistered hooks are pruned."""
        self._hooks[event] = list(hooks)
        if configs:
            self._hook_to_config.update(configs)
        self._prune_hook_configs()

    def _prune_hook_configs(self) -> None:
        """Drop config entries whose hook is no longer registered anywhere."""
        registered = set(self._global_hooks)
        for event_hooks in self._hooks.values():
            registered.update(event_hooks)
        self._hook_to_config = {
            hook: config
            for hook, config in self._hook_to_config.items()
            if hook in registered
        }

    def clear(self) -> None:
        """Drop the entire collection. Used by a reload to restart from scan."""
        self._hooks = defaultdict(list)
        self._global_hooks = []
        self._hook_configs = {}
        self._hook_to_config = {}

    def record_config(self, name: str, config: HookConfig) -> None:
        """Remember *config* by *name* for debugging (e.g. when hydrating)."""
        self._hook_configs[name] = config

    def get_hooks(self, event: HookEvent) -> list[HookCallable]:
        """Hooks for *event*, filtered by the ``CFG.LLM_HOOKS`` allowlist."""
        return self._filter(self._hooks[event])

    def get_global_hooks(self) -> list[HookCallable]:
        """Global hooks, filtered by the ``CFG.LLM_HOOKS`` allowlist."""
        return self._filter(self._global_hooks)

    def _filter(self, hooks: list[HookCallable]) -> list[HookCallable]:
        """Drop hooks hidden by the ``LLM_HOOKS`` allowlist."""
        allowed = list(CFG.LLM_HOOKS or [])
        if not allowed:
            return list(hooks)
        return [h for h in hooks if self._hook_name(h) in allowed]

    def _hook_name(self, hook: HookCallable) -> str:
        """The config name for *hook*, else its ``__name__``/``name``."""
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

    def has_hook_config(self, config: HookConfig) -> bool:
        """Whether this exact *config* object is registered here.

        By identity: a re-parse mints a fresh `HookConfig` that must still register.
        """
        return any(existing is config for existing in self._hook_to_config.values())


hook_registry = HookRegistry()
