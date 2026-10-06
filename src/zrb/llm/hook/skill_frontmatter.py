"""Hooks a skill declares in its frontmatter, replayed into every manager.

The skill scan runs once per process, so parsed configs are recorded here and
replayed by a factory seeded on every `HookManager`.

* A re-scan replaces a source's entry; a source the pass did not see is dropped.
* The factory skips configs a registry already holds, by config identity.
* A retired source is removed from every manager holding it; managers are held
  weakly so a per-run manager can be collected.
"""

from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from zrb.llm.hook.interface import HookCallable
    from zrb.llm.hook.manager import HookManager
    from zrb.llm.hook.schema import HookConfig

# Skill-frontmatter hook configs, by the skill file they came from.
_skill_hook_configs: dict[str, "list[HookConfig]"] = {}

# Sources seen by the scan pass in progress; `finish_skill_scan` drops the rest.
_scanned_sources: set[str] = set()

# Callables one manager holds for one source: `{source: [callable, ...]}`.
_SourceHooks: TypeAlias = "dict[str, list[HookCallable]]"

# What every live manager holds, by source. Weak keys: hydrated callables do not
# reference their manager, so a per-run manager can be collected.
_scan_manager_hooks: "weakref.WeakKeyDictionary[HookManager, _SourceHooks]" = (
    weakref.WeakKeyDictionary()
)


def start_skill_scan() -> None:
    """Open a scan pass. Anything `finish_skill_scan` does not see is dropped."""
    _scanned_sources.clear()


def apply_skill_frontmatter_hooks(
    manager: "HookManager", hooks_data: object, full_path: str
) -> None:
    """Parse a skill's `hooks:` block with *manager* and record it against *full_path*."""
    if isinstance(hooks_data, dict):
        configs = manager.build_claude_format_configs({"hooks": hooks_data}, full_path)
    elif isinstance(hooks_data, list):
        configs = manager.build_hook_configs(hooks_data, full_path)
    else:
        configs = []
    apply_skill_hook_configs(manager, full_path, configs)


def apply_skill_hook_configs(
    manager: "HookManager", source: str, configs: "list[HookConfig]"
) -> None:
    """Record and register *configs* as *source*'s hooks, replacing the old ones."""
    _scanned_sources.add(source)
    _unregister(source)
    if not configs:
        _skill_hook_configs.pop(source, None)
        return
    _skill_hook_configs[source] = list(configs)
    _register(manager, source, configs)


def finish_skill_scan() -> list[str]:
    """Close a scan pass, dropping hooks whose skill it did not find.

    Returns the dropped sources, for diagnostics and tests.
    """
    dropped = [
        source for source in _skill_hook_configs if source not in _scanned_sources
    ]
    for source in dropped:
        _unregister(source)
        del _skill_hook_configs[source]
    _scanned_sources.clear()
    return dropped


def get_skill_hook_configs() -> "list[HookConfig]":
    """Every recorded config, in source then scan order — for diagnostics and tests."""
    return [config for configs in _skill_hook_configs.values() for config in configs]


def reset_skill_hook_configs() -> None:
    """Drop everything recorded. For tests, and for a deliberate re-scan."""
    _skill_hook_configs.clear()
    _scanned_sources.clear()
    _scan_manager_hooks.clear()


def register_skill_frontmatter_hooks(manager: "HookManager") -> None:
    """Hook factory: register this process's skill-frontmatter hooks on *manager*."""
    for source, configs in _skill_hook_configs.items():
        registered = _register_configs(manager, source, configs)
        _record(manager, source, registered)


def _register(manager: "HookManager", source: str, configs: "list[HookConfig]") -> None:
    """Register *configs* on *manager*, remembering the callables."""
    _record(manager, source, _register_configs(manager, source, configs))


def _register_configs(
    manager: "HookManager", source: str, configs: "list[HookConfig]"
) -> "list[HookCallable]":
    """Register *configs* not already held, returning the new callables."""
    label = f"skill frontmatter ({source})"
    registered: "list[HookCallable]" = []
    for config in configs:
        if manager.registry.has_hook_config(config):
            continue
        hook = manager.register_hook_config(config, source=label)
        if hook is not None:
            registered.append(hook)
    return registered


def _record(
    manager: "HookManager", source: str, registered: "list[HookCallable]"
) -> None:
    """Remember *registered* as *source*'s hooks on *manager*, overwriting."""
    if not registered:
        return
    _scan_manager_hooks.setdefault(manager, {})[source] = registered


def _unregister(source: str) -> None:
    """Take *source*'s hooks out of every manager that holds them."""
    for manager, held in list(_scan_manager_hooks.items()):
        for hook in held.pop(source, []):
            manager.remove_hook(hook)
        if not held:
            del _scan_manager_hooks[manager]
