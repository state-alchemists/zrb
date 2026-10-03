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
* **A source is retired from the manager that actually holds its hooks.**
  Registering is the job of the manager a scan targets, but removal has to go to
  the manager the previous parse was registered on. `remove_hook` on any other
  manager is a silent no-op, so assuming the scan target left the earlier
  manager firing a rule its skill file no longer declares.

The canonical manager is *passed in* rather than imported: `hook.manager`
imports this module for the factory seed, so a module-level import of it here
would be a cycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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

# What the scan registered, by source, with the manager it registered them on.
# The owner is recorded rather than assumed: registering is the job of the
# manager a scan targets, but retiring a previous parse has to happen on
# whichever manager actually holds it — `remove_hook` on any other manager is a
# silent no-op, which would leave that manager firing a rule the skill file no
# longer declares.
_scan_manager_hooks: dict[str, "tuple[HookManager, list[HookCallable]]"] = {}


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
    dropped = [source for source in _skill_hook_configs if source not in _scanned_sources]
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
    second callable for the same rule.
    """
    for source, configs in _skill_hook_configs.items():
        label = f"skill frontmatter ({source})"
        for config in configs:
            if manager.registry.has_hook_config(config):
                continue
            manager.register_hook_config(config, source=label)


def _register(
    manager: "HookManager", source: str, configs: "list[HookConfig]"
) -> None:
    """Register *configs* on *manager*, remembering the callables.

    A config the registry already holds is skipped, the same guard the factory
    applies: both paths can meet, and neither may add a second callable for one
    rule.
    """
    label = f"skill frontmatter ({source})"
    registered: "list[HookCallable]" = []
    for config in configs:
        if manager.registry.has_hook_config(config):
            continue
        hook = manager.register_hook_config(config, source=label)
        if hook is not None:
            registered.append(hook)
    if registered:
        _scan_manager_hooks[source] = (manager, registered)


def _unregister(source: str) -> None:
    """Take *source*'s previously-registered hooks back out of their owner.

    The owner is the manager they were registered on, not whichever manager a
    later scan targets: only that manager holds these callables, and asking any
    other one to forget them does nothing at all.
    """
    recorded = _scan_manager_hooks.pop(source, None)
    if not recorded:
        return
    owner, hooks = recorded
    for hook in hooks:
        owner.remove_hook(hook)
