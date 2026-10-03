"""A skill's frontmatter `hooks:` block must fire on the per-run `HookManager`
an `LLMChatTask` builds, not only on the process-wide singleton it used to be
registered on — and it must survive a reload, and must not pile up across
scans."""

from pathlib import Path
from unittest.mock import patch

import pytest

from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.schema import CommandHookConfig, HookConfig
from zrb.llm.hook.skill_frontmatter import (
    apply_skill_hook_configs,
    get_skill_hook_configs,
    register_skill_frontmatter_hooks,
)
from zrb.llm.hook.types import HookEvent, HookType
from zrb.llm.skill.manager import SkillManager

# The flat shape names its hook, so a test can count *its* registrations without
# caring what else the default factories put on Stop (journal compliance and
# self-review are Stop hooks too).
_SKILL_FLAT_SHAPE = """---
name: hooked
hooks:
  - name: {name}
    events: [Stop]
    type: command
    config:
      command: echo fired >> {marker}
---
# body
"""

# The Claude shape has its hook name generated per parse, which is what makes
# accumulation visible.
_SKILL_CLAUDE_SHAPE = """---
name: hooked
hooks:
  Stop:
    - hooks:
        - type: command
          command: echo fired >> {marker}
---
# body
"""

_SKILL_WITHOUT_HOOKS = """---
name: hooked
---
# body
"""


def _write_skill(skill_dir: Path, content: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def _scan(skill_dir: Path, canonical: HookManager) -> None:
    """Scan *skill_dir*, with the process-wide manager the scan registers into
    replaced by *canonical*, so the real singleton stays clean."""
    with patch("zrb.llm.skill.manager.hook_manager", canonical):
        SkillManager(root_dir=str(skill_dir)).scan(search_dirs=[skill_dir])


def _stop_hook_names(manager: HookManager) -> list[str]:
    """The Stop hook config names on a manager, without triggering its load."""
    names = []
    for hook in manager.registry.get_hooks(HookEvent.STOP):
        config = manager.registry.get_hook_config(hook)
        if config is not None:
            names.append(config.name)
    return names


@pytest.mark.asyncio
async def test_claude_shape_hook_fires_on_a_fresh_per_run_manager(tmp_path):
    marker = tmp_path / "fired"
    canonical = HookManager(search_dirs=[])
    _write_skill(tmp_path / "skill", _SKILL_CLAUDE_SHAPE.format(marker=marker))
    _scan(tmp_path / "skill", canonical)
    # The scan's own manager still gets it — the singleton path is unchanged.
    assert _stop_hook_names(canonical), "scan did not register on its own manager"

    # A per-run manager has its own registry, so it only fires the hook if the
    # factory replays the recorded configs onto it.
    per_run = HookManager(search_dirs=[])
    await per_run.execute_hooks(HookEvent.STOP, {})
    assert _stop_hook_names(per_run), "skill hook was not replayed onto the run manager"
    assert marker.exists(), "replayed skill hook did not run"


@pytest.mark.asyncio
async def test_flat_shape_hook_fires_on_a_fresh_per_run_manager(tmp_path):
    marker = tmp_path / "fired"
    canonical = HookManager(search_dirs=[])
    _write_skill(
        tmp_path / "skill",
        _SKILL_FLAT_SHAPE.format(name="skill-flat-hook", marker=marker),
    )
    _scan(tmp_path / "skill", canonical)

    per_run = HookManager(search_dirs=[])
    await per_run.execute_hooks(HookEvent.STOP, {})
    assert "skill-flat-hook" in _stop_hook_names(per_run)
    assert marker.exists(), "replayed skill hook did not run"


def test_reload_keeps_skill_frontmatter_hooks(tmp_path):
    """`reload()` clears the canonical registry, so the factory has to put the
    skill hooks back — they are not in any hooks directory to be re-read."""
    canonical = HookManager(search_dirs=[])
    _write_skill(
        tmp_path / "skill",
        _SKILL_FLAT_SHAPE.format(name="skill-flat-hook", marker=tmp_path / "m"),
    )
    _scan(tmp_path / "skill", canonical)
    assert _stop_hook_names(canonical).count("skill-flat-hook") == 1

    canonical.reload()
    assert _stop_hook_names(canonical).count("skill-flat-hook") == 1, (
        "a reload dropped the skill's frontmatter hook"
    )


def test_rescan_replaces_a_claude_shaped_sources_hooks(tmp_path):
    """Every scan re-parses the file and mints fresh configs — a Claude-format
    hook gets a generated name per parse — so recording has to replace the
    source's entry rather than append to it."""
    canonical = HookManager(search_dirs=[])
    skill_dir = tmp_path / "skill"
    _write_skill(skill_dir, _SKILL_CLAUDE_SHAPE.format(marker=tmp_path / "m"))

    _scan(skill_dir, canonical)
    assert len(_stop_hook_names(canonical)) == 1
    assert len(get_skill_hook_configs()) == 1

    _scan(skill_dir, canonical)
    assert len(_stop_hook_names(canonical)) == 1, "the earlier parse is still firing"
    assert len(get_skill_hook_configs()) == 1


@pytest.mark.asyncio
async def test_rescan_does_not_fire_the_same_hook_twice(tmp_path):
    marker = tmp_path / "fired"
    skill_dir = tmp_path / "skill"
    _write_skill(
        skill_dir, _SKILL_FLAT_SHAPE.format(name="skill-flat-hook", marker=marker)
    )
    canonical = HookManager(search_dirs=[])

    _scan(skill_dir, canonical)
    _scan(skill_dir, canonical)
    await canonical.execute_hooks(HookEvent.STOP, {})
    assert marker.read_text(encoding="utf-8").count("fired") == 1


def test_rescan_drops_a_hook_removed_from_the_skill_file(tmp_path):
    canonical = HookManager(search_dirs=[])
    skill_dir = tmp_path / "skill"
    _write_skill(
        skill_dir,
        _SKILL_FLAT_SHAPE.format(name="skill-flat-hook", marker=tmp_path / "m"),
    )
    _scan(skill_dir, canonical)
    assert "skill-flat-hook" in _stop_hook_names(canonical)

    _write_skill(skill_dir, _SKILL_WITHOUT_HOOKS)
    _scan(skill_dir, canonical)
    assert "skill-flat-hook" not in _stop_hook_names(canonical), (
        "a deleted hook is still registered"
    )
    assert get_skill_hook_configs() == []


def test_scan_drops_hooks_of_a_skill_that_disappeared(tmp_path):
    canonical = HookManager(search_dirs=[])
    skill_dir = tmp_path / "skill"
    _write_skill(
        skill_dir,
        _SKILL_FLAT_SHAPE.format(name="skill-flat-hook", marker=tmp_path / "m"),
    )
    _scan(skill_dir, canonical)
    assert "skill-flat-hook" in _stop_hook_names(canonical)

    (skill_dir / "SKILL.md").unlink()
    _scan(skill_dir, canonical)
    assert "skill-flat-hook" not in _stop_hook_names(canonical)
    assert get_skill_hook_configs() == []


def test_a_config_already_on_the_registry_is_not_registered_twice(tmp_path):
    """The scan registers the canonical manager itself, and every manager also
    runs the factory on load, so the second registration has to be skipped."""
    canonical = HookManager(search_dirs=[])
    config = HookConfig(
        name="skill-hook-once",
        events=[HookEvent.STOP],
        type=HookType.COMMAND,
        config=CommandHookConfig(command="true"),
    )
    with patch("zrb.llm.skill.manager.hook_manager", canonical):
        canonical.register_hook_config(config, source="test")
        apply_skill_hook_configs(canonical, "some/SKILL.md", [config])
        register_skill_frontmatter_hooks(canonical)
    assert _stop_hook_names(canonical).count("skill-hook-once") == 1


def test_the_store_replays_onto_a_manager_over_its_own_registry(tmp_path):
    """A manager that is not the canonical one still gets the hooks — the
    registry identity no longer decides whether the replay happens."""
    canonical = HookManager(search_dirs=[])
    _write_skill(
        tmp_path / "skill",
        _SKILL_FLAT_SHAPE.format(name="skill-flat-hook", marker=tmp_path / "m"),
    )
    _scan(tmp_path / "skill", canonical)

    other = HookManager(search_dirs=[])
    assert _stop_hook_names(other) == []
    register_skill_frontmatter_hooks(other)
    assert _stop_hook_names(other) == ["skill-flat-hook"]
