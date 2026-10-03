"""Hooks a skill declares in its frontmatter, replayed into every manager.

A skill's `hooks:` block is process-wide configuration — it belongs to the skill
file, not to one session — but the scan that finds it runs once per process
(`SkillManager._scanned`), so the parsed `HookConfig`s are recorded here and
replayed by a factory seeded on every `HookManager` — the same seam the
journal-compliance and self-review hooks use. Registering them on the module
singleton alone, as the scan used to, put them out of reach of the fresh
per-run manager an `LLMChatTask` builds, so they never fired under
`zrb llm chat`.

Two managers are deliberately left out of the replay:

* One over the canonical `hook_registry` — the module singleton is the one.
  The scan registers into that registry directly (the pre-existing singleton
  behavior, unchanged), so replaying there would register every hook twice and
  fire it twice.
* One that already loaded its hooks. A skill file added mid-session is picked
  up by the next manager, or after `HookManager.reload()` — the same rule a
  changed `.zrb/hooks/` file follows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from zrb.llm.hook.registry import hook_registry

if TYPE_CHECKING:
    from zrb.llm.hook.manager import HookManager
    from zrb.llm.hook.schema import HookConfig

# Every skill-frontmatter hook this process has found, in scan order. Replayed
# onto each manager; never cleared by a scan, so a `SkillManager.reload()` that
# re-reads the same skill (a new random hook name each parse) is the way to drop
# a removed one.
_skill_hook_configs: list["HookConfig"] = []


def add_skill_hook_configs(configs: "list[HookConfig]") -> None:
    """Record *configs* for replay onto every later manager."""
    _skill_hook_configs.extend(configs)


def get_skill_hook_configs() -> "list[HookConfig]":
    """The recorded configs, in scan order — for diagnostics and tests."""
    return list(_skill_hook_configs)


def reset_skill_hook_configs() -> None:
    """Drop everything recorded. For tests, and for a deliberate re-scan."""
    _skill_hook_configs.clear()


def register_skill_frontmatter_hooks(manager: "HookManager") -> None:
    """Hook factory: register this process's skill-frontmatter hooks on *manager*.

    Seeded on every `HookManager` (see `HookManager.__init__`), so a per-run
    manager — `zrb llm chat`'s included — fires them.
    """
    if manager.registry is hook_registry:
        # The scan registered these into the canonical registry already.
        return
    for config in _skill_hook_configs:
        manager.register_hook_config(config, source="skill frontmatter")
