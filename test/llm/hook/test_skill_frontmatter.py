"Skill frontmatter hooks fire on per-run managers and survive rescans."

import gc
import weakref
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

_SKILL_FLAT_SHAPE = """---
name: hooked
hooks:
  - name: {name}
    events: [Stop]
    type: command
    config:
      command: echo fired >> {marker}
---
"""


_SKILL_CLAUDE_SHAPE = """---
name: hooked
hooks:
  Stop:
    - hooks:
        - type: command
          command: echo fired >> {marker}
---
"""

_SKILL_WITHOUT_HOOKS = """---
name: hooked
---
"""


def _write_skill(skill_dir: Path, content: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def _scan(skill_dir: Path, canonical: HookManager) -> None:
    "Scan *skill_dir*, with the process-wide manager the scan registers into"
    with patch("zrb.llm.skill.manager.hook_manager", canonical):
        SkillManager(root_dir=str(skill_dir)).scan(search_dirs=[skill_dir])


def _stop_hook_names(manager: HookManager) -> list[str]:
    "The Stop hook config names on a manager, without triggering its load."
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

    assert _stop_hook_names(canonical), "scan did not register on its own manager"

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
    assert (
        _stop_hook_names(canonical).count("skill-flat-hook") == 1
    ), "a reload dropped the skill's frontmatter hook"


def test_rescan_replaces_a_claude_shaped_sources_hooks(tmp_path):
    "Every scan re-parses the file and mints fresh configs — a Claude-format"
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
    assert "skill-flat-hook" not in _stop_hook_names(
        canonical
    ), "a deleted hook is still registered"
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
    "The scan registers the canonical manager itself, and every manager also"
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
    "A manager that is not the canonical one still gets the hooks — the"
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


def test_a_scan_on_another_manager_retires_the_first_managers_hooks(tmp_path):
    "Registering is the job of the manager a scan targets, but retiring the"
    first, second = HookManager(search_dirs=[]), HookManager(search_dirs=[])
    skill_dir = tmp_path / "skill"
    _write_skill(
        skill_dir,
        _SKILL_FLAT_SHAPE.format(name="skill-flat-hook", marker=tmp_path / "m"),
    )

    _scan(skill_dir, first)
    assert "skill-flat-hook" in _stop_hook_names(first)

    _scan(skill_dir, second)
    assert "skill-flat-hook" in _stop_hook_names(second)
    assert "skill-flat-hook" not in _stop_hook_names(
        first
    ), "the manager holding the previous parse still fires it"


def test_reload_replay_updates_the_recorded_callables(tmp_path):
    "`reload()` clears the registry and the factory registers the stored"
    canonical = HookManager(search_dirs=[])
    skill_dir = tmp_path / "skill"
    _write_skill(
        skill_dir,
        _SKILL_FLAT_SHAPE.format(name="skill-flat-hook", marker=tmp_path / "m"),
    )
    _scan(skill_dir, canonical)
    assert _stop_hook_names(canonical).count("skill-flat-hook") == 1

    canonical.reload()
    assert _stop_hook_names(canonical).count("skill-flat-hook") == 1

    _scan(skill_dir, canonical)
    assert (
        _stop_hook_names(canonical).count("skill-flat-hook") == 1
    ), "the reload's replay survived the re-scan — the rule now fires twice"


def test_a_manager_that_replayed_the_source_is_swept_too(tmp_path):
    """The factory installs a skill's hooks on every `HookManager`, so retiring a
    source has to reach all of them — not only the manager a scan targeted."""
    skill_dir = tmp_path / "skill"
    _write_skill(
        skill_dir,
        _SKILL_FLAT_SHAPE.format(name="skill-flat-hook", marker=tmp_path / "m"),
    )
    _scan(skill_dir, HookManager(search_dirs=[]))

    replayed = HookManager(search_dirs=[])
    replayed.reload()
    assert "skill-flat-hook" in _stop_hook_names(replayed)

    _write_skill(skill_dir, _SKILL_WITHOUT_HOOKS)
    _scan(skill_dir, HookManager(search_dirs=[]))

    assert "skill-flat-hook" not in _stop_hook_names(
        replayed
    ), "a manager that replayed the source kept firing the dropped rule"


def test_the_record_does_not_keep_a_scanned_manager_alive(tmp_path):
    "A scan can target a manager the caller then releases — a per-run manager"
    skill_dir = tmp_path / "skill"
    _write_skill(
        skill_dir,
        _SKILL_FLAT_SHAPE.format(name="skill-flat-hook", marker=tmp_path / "m"),
    )
    transient = HookManager(search_dirs=[])
    _scan(skill_dir, transient)
    assert "skill-flat-hook" in _stop_hook_names(transient)

    ref = weakref.ref(transient)
    del transient
    gc.collect()

    assert ref() is None, "the record still holds a manager the caller released"
