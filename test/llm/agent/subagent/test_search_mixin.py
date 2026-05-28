"""Tests for SubAgentManager.get_search_directories — exercises plugin/extra paths
and home/project search toggles that the smoke test in test_subagent_manager.py
doesn't cover."""

from unittest.mock import patch

import pytest

from zrb.llm.agent.subagent.manager import SubAgentManager


@pytest.fixture
def manager():
    return SubAgentManager()


def _make_plugin(plugin_root, name, with_agents_dir=True):
    p = plugin_root / name
    (p / ".claude-plugin").mkdir(parents=True)
    (p / ".claude-plugin" / "plugin.json").write_text("{}")
    if with_agents_dir:
        (p / "agents").mkdir()
    return p


def _project_with_agents(root):
    """Create root/.zrb/agents and root/.zrb/plugins/<plugin>/agents under root."""
    cfg_dir = root / ".zrb"
    (cfg_dir / "agents").mkdir(parents=True)
    _make_plugin(cfg_dir / "plugins", "p1")
    return cfg_dir


def test_get_search_directories_includes_extra_agent_dirs(manager, tmp_path):
    extra = tmp_path / "extras"
    extra.mkdir()
    with patch("zrb.llm.agent.subagent.manager.search_mixin.CFG") as cfg:
        cfg.LLM_SEARCH_HOME = False
        cfg.LLM_SEARCH_PROJECT = False
        cfg.LLM_CONFIG_DIR_NAMES = [".zrb"]
        cfg.LLM_PLUGIN_DIRS = []
        cfg.LLM_BASE_SEARCH_DIRS = []
        cfg.LLM_EXTRA_AGENT_DIRS = [str(extra)]
        dirs = [str(d) for d in manager.get_search_directories()]
    assert any(str(extra) in d for d in dirs)


def test_get_search_directories_skips_missing_extra_dir(manager, tmp_path):
    with patch("zrb.llm.agent.subagent.manager.search_mixin.CFG") as cfg:
        cfg.LLM_SEARCH_HOME = False
        cfg.LLM_SEARCH_PROJECT = False
        cfg.LLM_CONFIG_DIR_NAMES = [".zrb"]
        cfg.LLM_PLUGIN_DIRS = []
        cfg.LLM_BASE_SEARCH_DIRS = []
        cfg.LLM_EXTRA_AGENT_DIRS = [str(tmp_path / "ghost")]
        dirs = [str(d) for d in manager.get_search_directories()]
    # ghost path is silently skipped
    assert not any("ghost" in d for d in dirs)


def test_get_search_directories_includes_plugin_agents(manager, tmp_path):
    plugins_root = tmp_path / "plugins"
    plugins_root.mkdir()
    _make_plugin(plugins_root, "with-agents", with_agents_dir=True)
    _make_plugin(plugins_root, "without-agents", with_agents_dir=False)

    with patch("zrb.llm.agent.subagent.manager.search_mixin.CFG") as cfg:
        cfg.LLM_SEARCH_HOME = False
        cfg.LLM_SEARCH_PROJECT = False
        cfg.LLM_CONFIG_DIR_NAMES = [".zrb"]
        cfg.LLM_PLUGIN_DIRS = [str(plugins_root)]
        cfg.LLM_BASE_SEARCH_DIRS = []
        cfg.LLM_EXTRA_AGENT_DIRS = []
        dirs = [str(d) for d in manager.get_search_directories()]

    # Plugin with /agents shows up; plugin without doesn't
    assert any("with-agents/agents" in d for d in dirs)
    assert not any("without-agents/agents" in d for d in dirs)


def test_get_search_directories_walks_project_hierarchy(manager, tmp_path):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    _project_with_agents(tmp_path / "a")
    manager._root_dir = str(nested)

    with patch("zrb.llm.agent.subagent.manager.search_mixin.CFG") as cfg:
        cfg.LLM_SEARCH_HOME = False
        cfg.LLM_SEARCH_PROJECT = True
        cfg.LLM_CONFIG_DIR_NAMES = [".zrb"]
        cfg.LLM_PLUGIN_DIRS = []
        cfg.LLM_BASE_SEARCH_DIRS = []
        cfg.LLM_EXTRA_AGENT_DIRS = []
        dirs = [str(d) for d in manager.get_search_directories()]

    # The nested /agents dir from the project traversal shows up
    assert any(".zrb/agents" in d for d in dirs)
    # And the plugin under .zrb/plugins
    assert any(".zrb/plugins/p1/agents" in d for d in dirs)
