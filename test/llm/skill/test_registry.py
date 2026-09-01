"""Tests for the `SkillRegistry` split-out (ADR-0090).

A registry is the canonical skill collection: it stores manual registrations and
discovered skills, merges them on query, and never scans files itself — that is
`SkillManager`'s job. Since both layers are public only via `SkillManager`, most
tests drive the registry through a manager that shares it (the public boundary),
mirroring how `zrb_init.py` and the module singleton wire up.
"""

import pytest

from zrb.llm.skill.manager import Skill, SkillManager
from zrb.llm.skill.registry import SkillRegistry, skill_registry


@pytest.fixture
def registry():
    return SkillRegistry()


@pytest.fixture
def skill():
    return Skill(name="alpha", path="/p/alpha.md", description="A skill")


@pytest.fixture
def manager(registry):
    manager = SkillManager(registry=registry, root_dir="/nonexistent")
    manager.scan(search_dirs=[])
    return manager


def _skill(name, **kwargs):
    kwargs.setdefault("path", f"/p/{name}")
    kwargs.setdefault("description", "d")
    return Skill(name=name, **kwargs)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_registry_constructed_empty(registry):
    assert registry.get_skills() == []


def test_registry_starts_with_skills():
    reg = SkillRegistry(skills=[_skill("a"), _skill("b")])
    assert [s.name for s in reg.get_skills()] == ["a", "b"]


def test_manager_defaults_to_fresh_isolated_registry():
    manager = SkillManager()
    assert manager.registry is not skill_registry
    another = SkillManager()
    assert another.registry is not manager.registry


def test_singleton_is_skill_registry():
    assert isinstance(skill_registry, SkillRegistry)


# ---------------------------------------------------------------------------
# add_skill / get_skill / get_skills
# ---------------------------------------------------------------------------


def test_add_then_get(manager, skill):
    manager.add_skill(skill)
    assert manager.get_skill("alpha") is skill


def test_added_skill_listed(manager, skill):
    manager.add_skill(skill)
    assert manager.get_skills() == [skill]


def test_add_overrides_existing_name(manager, skill):
    manager.add_skill(skill)
    replacement = _skill("alpha", path="/p/replacement")
    manager.add_skill(replacement)
    assert manager.get_skill("alpha") is replacement


def test_get_matches_by_path(manager, skill):
    manager.add_skill(skill)
    assert manager.get_skill("/p/alpha.md") is skill


def test_get_unknown(manager):
    assert manager.get_skill("nope") is None


# ---------------------------------------------------------------------------
# remove_skill
# ---------------------------------------------------------------------------


def test_remove_skill(manager, skill):
    manager.add_skill(skill)
    manager.remove_skill("alpha")
    assert manager.get_skill("alpha") is None
    assert manager.get_skills() == []


def test_remove_unknown_is_noop(manager):
    manager.remove_skill("missing")


def test_remove_then_scan_rediscovers_file(manager, skill, tmp_path):
    manager.add_skill(skill)
    (tmp_path / "gone.skill.md").write_text("# Gone")
    manager.scan(search_dirs=[tmp_path])
    manager.remove_skill("Gone")
    assert manager.get_skill("Gone") is None
    manager.scan(search_dirs=[tmp_path])
    assert manager.get_skill("Gone") is not None


# ---------------------------------------------------------------------------
# set_skills (replacement, ADR-0090 Part 3)
# ---------------------------------------------------------------------------


def test_set_skills_replaces_whole_collection(manager, skill):
    manager.add_skill(skill)
    manager.set_skills([_skill("beta"), _skill("gamma")])
    assert [s.name for s in manager.get_skills()] == ["beta", "gamma"]


def test_set_skills_with_deferred_callable(manager):
    manager.set_skills(lambda: [_skill("late")])
    assert manager.get_skill("late") is not None


def test_set_skills_deferred_resolves_at_query_time(registry):
    values = [_skill("first")]
    registry.set_skills(lambda: values)
    assert registry.get_skills() == values
    values = [_skill("second")]
    assert [s.name for s in registry.get_skills()] == ["second"]


def test_manual_survives_scan(manager, skill, tmp_path):
    manager.add_skill(skill)
    (tmp_path / "found.skill.md").write_text("# Found")
    manager.scan(search_dirs=[tmp_path])
    assert manager.get_skill("alpha") is skill
    assert manager.get_skill("Found") is not None


def test_manual_wins_name_collision_with_discovered(manager, skill, tmp_path):
    manager.add_skill(skill)
    (tmp_path / "alpha.skill.md").write_text("# Alpha")
    manager.scan(search_dirs=[tmp_path])
    assert manager.get_skill("alpha") is skill


# ---------------------------------------------------------------------------
# clear_discovered
# ---------------------------------------------------------------------------


def test_reload_keeps_manual(manager, skill, tmp_path):
    manager.add_skill(skill)
    (tmp_path / "found.skill.md").write_text("# Found")
    manager.scan(search_dirs=[tmp_path])
    manager.reload()
    assert manager.get_skill("alpha") is skill


# ---------------------------------------------------------------------------
# LLM_SKILLS twin
# ---------------------------------------------------------------------------


def test_llm_skills_allowlist_filters_visible_skills(registry, monkeypatch):
    registry.add_skill(_skill("alpha"))
    registry.add_skill(_skill("beta"))
    monkeypatch.setenv("ZRB_LLM_SKILLS", "alpha")
    assert [s.name for s in registry.get_skills()] == ["alpha"]
    assert registry.get_skill("beta") is None
    monkeypatch.setenv("ZRB_LLM_SKILLS", "")
    assert {s.name for s in registry.get_skills()} == {"alpha", "beta"}
