"""A skill's frontmatter `hooks:` block must fire on the per-run `HookManager`
an `LLMChatTask` builds, not only on the process-wide singleton it used to be
registered on."""

from unittest.mock import patch

import pytest

from zrb.llm.hook.manager import HookManager, hook_manager
from zrb.llm.hook.registry import hook_registry
from zrb.llm.hook.schema import CommandHookConfig, HookConfig
from zrb.llm.hook.skill_frontmatter import add_skill_hook_configs
from zrb.llm.hook.types import HookEvent, HookType
from zrb.llm.skill.manager import SkillManager

_SKILL_CLAUDE_SHAPE = """---
name: hooked
hooks:
  Stop:
    - hooks:
        - type: command
          command: echo fired > {marker}
---
# body
"""

_SKILL_FLAT_SHAPE = """---
name: hooked
hooks:
  - name: skill-flat-hook
    events: [Stop]
    type: command
    config:
      command: echo fired > {marker}
---
# body
"""


def _scan_skill(skill_dir, content: str) -> HookManager:
    """Write *content* as a SKILL.md, scan it, and return the manager the scan
    registered into (an isolated one, so the canonical registry stays clean)."""
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    scan_target = HookManager(search_dirs=[])
    with patch("zrb.llm.skill.manager.hook_manager", scan_target):
        SkillManager(root_dir=str(skill_dir)).scan(search_dirs=[skill_dir])
    return scan_target


def _stop_hook_names(manager: HookManager) -> list[str]:
    names = []
    for hook in manager.registry.get_hooks(HookEvent.STOP):
        config = manager.registry.get_hook_config(hook)
        if config is not None:
            names.append(config.name)
    return names


@pytest.mark.asyncio
async def test_claude_shape_hook_fires_on_a_fresh_per_run_manager(tmp_path):
    marker = tmp_path / "fired"
    scan_target = _scan_skill(
        tmp_path / "skill", _SKILL_CLAUDE_SHAPE.format(marker=marker)
    )
    # The scan's own manager still gets it — the singleton path is unchanged.
    assert _stop_hook_names(scan_target), "scan did not register on its own manager"

    # A per-run manager has its own registry, so it only fires the hook if the
    # factory replays the recorded configs onto it.
    per_run = HookManager(search_dirs=[])
    await per_run.execute_hooks(HookEvent.STOP, {})
    assert _stop_hook_names(per_run), "skill hook was not replayed onto the run manager"
    assert marker.exists(), "replayed skill hook did not run"


@pytest.mark.asyncio
async def test_flat_shape_hook_fires_on_a_fresh_per_run_manager(tmp_path):
    marker = tmp_path / "fired"
    _scan_skill(tmp_path / "skill", _SKILL_FLAT_SHAPE.format(marker=marker))
    per_run = HookManager(search_dirs=[])
    await per_run.execute_hooks(HookEvent.STOP, {})
    assert "skill-flat-hook" in _stop_hook_names(per_run)
    assert marker.exists(), "replayed skill hook did not run"


@pytest.mark.asyncio
async def test_recorded_hooks_are_not_replayed_into_the_canonical_registry():
    """The scan registers into `hook_registry` itself, so replaying there would
    register every skill hook a second time and fire it twice."""
    add_skill_hook_configs(
        [
            HookConfig(
                name="skill-hook-once",
                events=[HookEvent.STOP],
                type=HookType.COMMAND,
                config=CommandHookConfig(command="true"),
            )
        ]
    )
    assert "skill-hook-once" not in _stop_hook_names(hook_manager)
    await HookManager(search_dirs=[], registry=hook_registry).execute_hooks(
        HookEvent.STOP, {}
    )
    assert "skill-hook-once" not in _stop_hook_names(hook_manager)
