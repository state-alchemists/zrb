"""Hooks a skill declares in its frontmatter, replayed into every manager.

A skill's `hooks:` block is process-wide configuration — it belongs to the skill
file, not to one session — but the scan that finds it runs once per process
(`SkillManager._scanned`), so the parsed `HookConfig`s are recorded here and
replayed by a factory seeded on every `HookManager` — the same seam the
journal-compliance and self-review hooks use. Registering them on the module
singleton alone, as the scan used to, put them out of reach of the fresh
per-run manager an `LLMChatTask` builds, so they never fired under
`zrb llm chat`.

Three rules this store has to keep, each one a defect it used to have:

* **A source replaces its entry, and an unseen source is dropped.** A re-scan
  re-parses the same file and mints fresh configs (a Claude-format hook gets a
  generated name per parse), so appending would leave the previous parse's
  hooks in place — firing the same rule twice, and keeping one alive after it
  was edited out of the file. `start_skill_scan`/`finish_skill_scan` bound the
  pass, so a hook whose skill is gone goes with it.
* **The factory replays by config identity, never by registry identity.** A
  registry that is empty because `HookManager.reload()` just cleared it still
  needs the replay; skipping on `manager.registry is hook_registry` skipped it
  there too, so a reload silently dropped every skill hook.
* **A source is retired from every manager holding it, and no manager is kept
  alive by the record.** The factory installs a skill's hooks on *every*
  `HookManager`, so removal has to reach all of them; sweeping only the manager a
  scan last targeted left the rest firing a rule its skill file no longer
  declares. The record is keyed by manager and held weakly, so a per-run manager
  is swept while it lives and costs nothing once the caller lets it go.

The canonical manager is *passed in* rather than imported: `hook.manager`
imports this module for the factory seed, so a module-level import of it here
would be a cycle.
"""

from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from zrb.llm.hook.interface import HookCallable
    from zrb.llm.hook.manager import HookManager
    from zrb.llm.hook.schema import HookConfig

# Every skill-frontmatter hook the current scan pass found, by the skill file it
# came from. Keyed rather than listed so a re-scan replaces a source instead of
# stacking another copy of it.
_skill_hook_configs: dict[str, "list[HookConfig]"] = {}

# Sources seen by the scan pass in progress; `finish_skill_scan` drops the rest.
_scanned_sources: set[str] = set()

# Callables one manager holds for one source: `{source: [callable, ...]}`.
_SourceHooks: TypeAlias = "dict[str, list[HookCallable]]"

# What every live manager holds, by source. Keyed by manager, and held weakly:
# the factory installs a skill's hooks on every `HookManager`, so retiring one
# has to sweep all of them — while a per-run manager must not be kept alive by
# this record. A hydrated callable does not reference the manager it came from
# (`_wrap_with_matchers` closes over the config alone), so the weak key is what
# lets that manager be collected.
_scan_manager_hooks: "weakref.WeakKeyDictionary[HookManager, _SourceHooks]" = (
    weakref.WeakKeyDictionary()
)


def start_skill_scan() -> None:
    """Open a scan pass. Anything `finish_skill_scan` does not see is dropped."""
    _scanned_sources.clear()


def apply_skill_frontmatter_hooks(
    manager: "HookManager", hooks_data: object, full_path: str
) -> None:
    """Parse a skill's `hooks:` block and record it against *full_path*.

    The scan's whole entry point, so parsing and registering can never end up
    pointed at different managers: *manager* is the one the scan registers into,
    and the one whose config builders parse the block.
    """
    if isinstance(hooks_data, dict):
        configs = manager.build_claude_format_configs({"hooks": hooks_data}, full_path)
    elif isinstance(hooks_data, list):
        # Zrb flat format
        configs = manager.build_hook_configs(hooks_data, full_path)
    else:
        # No `hooks:` block, or one in a shape we do not understand.
        configs = []
    apply_skill_hook_configs(manager, full_path, configs)


def apply_skill_hook_configs(
    manager: "HookManager", source: str, configs: "list[HookConfig]"
) -> None:
    """Record *configs* as *source*'s hooks, replacing whatever that source had.

    Registers them on *manager* as the scan always has, taking the source's
    previous registration out first so a re-scan does not leave the earlier
    parse firing alongside the new one.
    """
    _scanned_sources.add(source)
    _unregister(source)
    if not configs:
        # A skill that dropped its `hooks:` block, or never had one.
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
    """Hook factory: register this process's skill-frontmatter hooks on *manager*.

    Seeded on every `HookManager` (see `HookManager.__init__`), so a per-run
    manager — `zrb llm chat`'s included — fires them, and so the manager the scan
    writes to gets them back after a `reload()` cleared its registry.

    A config the manager's registry already holds is skipped by identity: the
    scan registers that one directly, and this factory would otherwise add a
    second callable for the same rule. What it does register is recorded against
    *manager* when that manager already owns the source, so a `reload()` — which
    clears the registry and re-registers fresh callables — leaves the record
    pointing at the live ones (see `_record`).
    """
    for source, configs in _skill_hook_configs.items():
        registered = _register_configs(manager, source, configs)
        _record(manager, source, registered)


def _register(manager: "HookManager", source: str, configs: "list[HookConfig]") -> None:
    """Register *configs* on *manager*, remembering the callables."""
    _record(manager, source, _register_configs(manager, source, configs))


def _register_configs(
    manager: "HookManager", source: str, configs: "list[HookConfig]"
) -> "list[HookCallable]":
    """Register *configs* on *manager*, returning the callables that landed.

    A config the registry already holds is skipped, the guard both callers need:
    the scan and the factory can meet on the same rule, and neither may add a
    second callable for it.
    """
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
    """Remember *registered* as *source*'s hooks on *manager*.

    Every manager that ends up holding a source is recorded, not just the one a
    scan targeted: the factory installs the same configs on all of them, so a
    retirement that swept only the scan target left the others firing a rule the
    skill file no longer declares. Overwriting is what keeps the record honest
    across a `reload()`, whose replay registers the stored configs again as new
    callables — the cleared ones it used to name would remove nothing.
    """
    if not registered:
        return
    _scan_manager_hooks.setdefault(manager, {})[source] = registered


def _unregister(source: str) -> None:
    """Take *source*'s hooks out of every manager that holds them.

    All of them, not just the manager a later scan targets: the factory installs
    a skill's hooks on every `HookManager`, and a manager that is no longer
    scanned still holds its callables. It is dropped from the record once it
    holds nothing, so the bookkeeping does not outlive the hooks.
    """
    for manager, held in list(_scan_manager_hooks.items()):
        for hook in held.pop(source, []):
            manager.remove_hook(hook)
        if not held:
            del _scan_manager_hooks[manager]
