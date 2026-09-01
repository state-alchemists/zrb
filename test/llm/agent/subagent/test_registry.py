"""Tests for the `SubAgentRegistry` split-out (ADR-0090).

A registry is the canonical sub-agent definition collection: it stores manual
registrations and discovered definitions, merges them on query, and never scans
files itself — that is `SubAgentManager`'s job. Since both layers are public
only via `SubAgentManager`, most tests drive the registry through a manager that
shares it (the public boundary), mirroring how `zrb_init.py` and the module
singleton wire up.
"""

import pytest

from zrb.llm.agent.subagent.definition import SubAgentDefinition
from zrb.llm.agent.subagent.manager import SubAgentManager
from zrb.llm.agent.subagent.registry import SubAgentRegistry, sub_agent_registry


@pytest.fixture
def registry():
    return SubAgentRegistry()


@pytest.fixture
def manager(registry):
    manager = SubAgentManager(registry=registry, root_dir="/nonexistent")
    manager.scan(search_dirs=[])
    return manager


def _agent(name, **kwargs):
    kwargs.setdefault("path", f"/p/{name}")
    kwargs.setdefault("description", "d")
    kwargs.setdefault("system_prompt", "p")
    return SubAgentDefinition(name=name, **kwargs)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_registry_constructed_empty(registry):
    assert registry.get_agents() == []


def test_registry_starts_with_agents():
    reg = SubAgentRegistry(agents=[_agent("a"), _agent("b")])
    assert [a.name for a in reg.get_agents()] == ["a", "b"]


def test_manager_defaults_to_fresh_isolated_registry():
    manager = SubAgentManager()
    assert manager.registry is not sub_agent_registry
    another = SubAgentManager()
    assert another.registry is not manager.registry


def test_singleton_is_sub_agent_registry():
    assert isinstance(sub_agent_registry, SubAgentRegistry)


# ---------------------------------------------------------------------------
# add_agent / get_agent_definition / get_agents
# ---------------------------------------------------------------------------


def test_add_then_get(manager):
    agent = _agent("alpha")
    manager.add_agent(agent)
    assert manager.get_agent_definition("alpha") is agent


def test_added_agent_listed(manager):
    agent = _agent("alpha")
    manager.add_agent(agent)
    assert manager.get_agents() == [agent]


def test_add_overrides_existing_name(manager):
    manager.add_agent(_agent("alpha", path="/p/orig"))
    replacement = _agent("alpha", path="/p/replacement")
    manager.add_agent(replacement)
    assert manager.get_agent_definition("alpha") is replacement


def test_get_matches_by_path(manager):
    agent = _agent("alpha")
    manager.add_agent(agent)
    assert manager.get_agent_definition("/p/alpha") is agent


def test_get_unknown(manager):
    assert manager.get_agent_definition("nope") is None


# ---------------------------------------------------------------------------
# remove_agent
# ---------------------------------------------------------------------------


def test_remove_agent(manager):
    manager.add_agent(_agent("alpha"))
    manager.remove_agent("alpha")
    assert manager.get_agent_definition("alpha") is None
    assert manager.get_agents() == []


def test_remove_unknown_is_noop(manager):
    manager.remove_agent("missing")


# ---------------------------------------------------------------------------
# set_agents (replacement, ADR-0090 Part 3)
# ---------------------------------------------------------------------------


def test_set_agents_replaces_whole_collection(manager):
    manager.add_agent(_agent("alpha"))
    manager.set_agents([_agent("beta"), _agent("gamma")])
    assert [a.name for a in manager.get_agents()] == ["beta", "gamma"]


def test_set_agents_with_deferred_callable(manager):
    manager.set_agents(lambda: [_agent("late")])
    assert manager.get_agent_definition("late") is not None


def test_set_agents_deferred_resolves_at_query_time(registry):
    values = [_agent("first")]
    registry.set_agents(lambda: values)
    assert registry.get_agents() == values
    values = [_agent("second")]
    assert [a.name for a in registry.get_agents()] == ["second"]


# ---------------------------------------------------------------------------
# Manual survives scan / discovery merge
# ---------------------------------------------------------------------------


def test_manual_survives_scan(tmp_path):
    manager = SubAgentManager(
        registry=SubAgentRegistry(), root_dir="/nonexistent", max_depth=3
    )
    manager.scan(search_dirs=[])
    manager.add_agent(_agent("alpha"))
    (tmp_path / "agents" / "found").mkdir(parents=True)
    (tmp_path / "agents" / "found" / "AGENT.md").write_text("# Found")
    manager.scan(search_dirs=[tmp_path])
    assert manager.get_agent_definition("alpha") is not None
    assert manager.get_agent_definition("Found") is not None


def test_manual_wins_name_collision_with_discovered(tmp_path):
    manager = SubAgentManager(
        registry=SubAgentRegistry(), root_dir="/nonexistent", max_depth=3
    )
    manager.scan(search_dirs=[])
    manager.add_agent(_agent("alpha", path="/p/manual"))
    (tmp_path / "agents" / "alpha").mkdir(parents=True)
    (tmp_path / "agents" / "alpha" / "AGENT.md").write_text("# Alpha")
    manager.scan(search_dirs=[tmp_path])
    assert manager.get_agent_definition("alpha").path == "/p/manual"


def test_reload_keeps_manual(manager):
    agent = _agent("alpha")
    manager.add_agent(agent)
    manager.reload()
    assert manager.get_agent_definition("alpha") is agent


# ---------------------------------------------------------------------------
# LLM_AGENTS twin
# ---------------------------------------------------------------------------


def test_llm_agents_allowlist_filters_roster(manager, monkeypatch):
    manager.add_agent(_agent("alpha"))
    manager.add_agent(_agent("beta"))
    monkeypatch.setenv("ZRB_LLM_AGENTS", "alpha")
    assert [a.name for a in manager.get_agents()] == ["alpha"]
    assert manager.get_agent_definition("beta") is None
    monkeypatch.setenv("ZRB_LLM_AGENTS", "")
    assert {a.name for a in manager.get_agents()} == {"alpha", "beta"}
