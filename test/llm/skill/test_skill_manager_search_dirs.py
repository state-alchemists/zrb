from unittest.mock import patch

import pytest

from zrb.llm.skill.manager import SkillManager
from zrb.llm.skill.manager import skill_manager as skill_manager_singleton


@pytest.fixture
def skill_manager(tmp_path):
    return SkillManager(root_dir=str(tmp_path))


def _builtin_mock_cfg(mock_cfg, *, enable_builtin_skills, extra_skill_dirs=None):
    """Configure a mocked CFG that disables home/project search so only the
    builtin (and any extra) directories drive discovery."""
    mock_cfg.ROOT_GROUP_NAME = "zrb"
    mock_cfg.LLM_SEARCH_HOME = False
    mock_cfg.LLM_SEARCH_PROJECT = False
    mock_cfg.LLM_CONFIG_DIR_NAMES = [".claude", ".zrb"]
    mock_cfg.LLM_PLUGIN_DIRS = []
    mock_cfg.LLM_BASE_SEARCH_DIRS = []
    mock_cfg.LLM_EXTRA_SKILL_DIRS = extra_skill_dirs or []
    mock_cfg.LLM_ENABLE_BUILTIN_SKILLS = enable_builtin_skills


@pytest.fixture
def manager(tmp_path):
    return SkillManager(root_dir=str(tmp_path))


def _mock_cfg(mock_cfg, **overrides):
    mock_cfg.ROOT_GROUP_NAME = "zrb"
    mock_cfg.LLM_SEARCH_HOME = False
    mock_cfg.LLM_SEARCH_PROJECT = False
    mock_cfg.LLM_CONFIG_DIR_NAMES = [".claude", ".zrb"]
    mock_cfg.LLM_PLUGIN_DIRS = []
    mock_cfg.LLM_BASE_SEARCH_DIRS = []
    mock_cfg.LLM_EXTRA_SKILL_DIRS = []
    mock_cfg.LLM_ENABLE_BUILTIN_SKILLS = False
    for key, value in overrides.items():
        setattr(mock_cfg, key, value)


def test_get_search_directories_home_plugins(tmp_path):
    home = tmp_path / "home"
    plugin = home / ".claude" / "plugins" / "hp"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text('{"name": "hp"}')
    (plugin / "skills").mkdir(parents=True)
    manager = SkillManager(root_dir=str(tmp_path))
    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        _mock_cfg(mock_cfg, LLM_SEARCH_HOME=True)
        with patch("zrb.llm.skill.manager.Path.home", return_value=home):
            dirs = [str(d).replace("\\", "/") for d in manager.search_dirs]
    assert any(d.endswith("hp/skills") for d in dirs)


def test_get_search_directories_includes_root(tmp_path):
    manager = SkillManager(root_dir=str(tmp_path))
    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        _mock_cfg(mock_cfg)
        dirs = [str(d) for d in manager.search_dirs]
    assert str(tmp_path) in dirs


def test_builtin_core_skills_always_searched(tmp_path):
    manager = SkillManager(root_dir=str(tmp_path))
    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        _mock_cfg(mock_cfg, LLM_ENABLE_BUILTIN_SKILLS=False)
        dirs = [str(d).replace("\\", "/") for d in manager.search_dirs]
    assert any(d.endswith("llm_plugin/core_skills") for d in dirs)
    assert not any(d.endswith("llm_plugin/skills") for d in dirs)


def test_no_builtin_journaling_skill_ships(tmp_path):
    """The journal is a pair of tools now, not a skill.

    `core-journaling` carried the on-disk format the writers own by
    construction; keeping a stale copy would give the model a second, divergent
    description of the same tree.
    """
    manager = SkillManager(root_dir=str(tmp_path))
    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        _builtin_mock_cfg(mock_cfg, enable_builtin_skills=False)
        names = {s.name for s in manager.scan()}
    assert "core-journaling" not in names
    assert "core-coding" in names, "unrelated core skills must be unaffected"


def test_a_user_journaling_skill_still_loads(tmp_path):
    """Deleting the built-in must not blocklist the name (ADR-0054)."""
    user_dir = tmp_path / "skills" / "core-journaling"
    user_dir.mkdir(parents=True)
    (user_dir / "SKILL.md").write_text(
        "---\nname: core-journaling\ndescription: mine\n---\n# Mine\n",
        encoding="utf-8",
    )
    manager = SkillManager(root_dir=str(tmp_path))
    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        _builtin_mock_cfg(
            mock_cfg,
            enable_builtin_skills=False,
            extra_skill_dirs=[str(tmp_path / "skills")],
        )
        skills = {s.name: s for s in manager.scan()}
    assert skills["core-journaling"].description == "mine"


def test_builtin_utility_skills_searched_when_enabled(tmp_path):
    manager = SkillManager(root_dir=str(tmp_path))
    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        _mock_cfg(mock_cfg, LLM_ENABLE_BUILTIN_SKILLS=True)
        dirs = [str(d).replace("\\", "/") for d in manager.search_dirs]
    assert any(d.endswith("llm_plugin/core_skills") for d in dirs)
    assert any(d.endswith("llm_plugin/skills") for d in dirs)
