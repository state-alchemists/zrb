import json
from unittest.mock import patch

import pytest

from zrb.llm.skill.manager import SkillManager
from zrb.llm.skill.manager import skill_manager as skill_manager_singleton


@pytest.fixture
def skill_manager(tmp_path):
    return SkillManager(root_dir=str(tmp_path))


def _builtin_mock_cfg(mock_cfg, *, enable_builtin_skills, extra_skill_dirs=None):
    "Configure a mocked CFG that disables home/project search so only the"
    mock_cfg.ROOT_GROUP_NAME = "zrb"
    mock_cfg.LLM_SEARCH_HOME_ENABLED = False
    mock_cfg.LLM_SEARCH_PROJECT_ENABLED = False
    mock_cfg.LLM_CONFIG_DIR_NAMES = [".claude", ".zrb"]
    mock_cfg.LLM_PLUGIN_DIRS = []
    mock_cfg.LLM_BASE_SEARCH_DIRS = []
    mock_cfg.LLM_EXTRA_SKILL_DIRS = extra_skill_dirs or []
    mock_cfg.LLM_BUILTIN_SKILLS_ENABLED = enable_builtin_skills


@pytest.fixture
def manager(tmp_path):
    return SkillManager(root_dir=str(tmp_path))


def _mock_cfg(mock_cfg, **overrides):
    mock_cfg.ROOT_GROUP_NAME = "zrb"
    mock_cfg.LLM_SEARCH_HOME_ENABLED = False
    mock_cfg.LLM_SEARCH_PROJECT_ENABLED = False
    mock_cfg.LLM_CONFIG_DIR_NAMES = [".claude", ".zrb"]
    mock_cfg.LLM_PLUGIN_DIRS = []
    mock_cfg.LLM_BASE_SEARCH_DIRS = []
    mock_cfg.LLM_EXTRA_SKILL_DIRS = []
    mock_cfg.LLM_BUILTIN_SKILLS_ENABLED = False
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
        _mock_cfg(mock_cfg, LLM_SEARCH_HOME_ENABLED=True)
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
        _mock_cfg(mock_cfg, LLM_BUILTIN_SKILLS_ENABLED=False)
        dirs = [str(d).replace("\\", "/") for d in manager.search_dirs]
    assert any(d.endswith("llm_plugin/core_skills") for d in dirs)
    assert not any(d.endswith("llm_plugin/skills") for d in dirs)


def test_no_builtin_journaling_skill_ships(tmp_path):
    "The journal is a pair of tools now, not a skill."
    manager = SkillManager(root_dir=str(tmp_path))
    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        _builtin_mock_cfg(mock_cfg, enable_builtin_skills=False)
        names = {s.name for s in manager.scan()}
    assert "core-journaling" not in names
    assert "core-coding" in names, "unrelated core skills must be unaffected"


def test_a_user_journaling_skill_still_loads(tmp_path):
    "Deleting the built-in must not blocklist the name (ADR-0054)."
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
        _mock_cfg(mock_cfg, LLM_BUILTIN_SKILLS_ENABLED=True)
        dirs = [str(d).replace("\\", "/") for d in manager.search_dirs]
    assert any(d.endswith("llm_plugin/core_skills") for d in dirs)
    assert any(d.endswith("llm_plugin/skills") for d in dirs)


def _write_skill(skill_dir, name, description):
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n# {name}\n",
        encoding="utf-8",
    )


def _scan_home_skills(home, tmp_path):
    "Scan with the home search pointed at *home* and every other source off."
    manager = SkillManager(root_dir=str(tmp_path))
    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        _mock_cfg(mock_cfg, LLM_SEARCH_HOME_ENABLED=True)
        with patch("zrb.llm.skill.manager.Path.home", return_value=home):
            return {skill.name: skill for skill in manager.scan()}


def test_synced_skills_are_scanned(tmp_path):
    "claude.ai downloads sit in synced/<bucket>/<name>/SKILL.md, one level deeper."
    home = tmp_path / "home"
    bucket = home / ".claude" / "skills" / "synced" / "bucket-id"
    _write_skill(bucket / "pdf", "pdf", "from claude.ai")
    skills = _scan_home_skills(home, tmp_path)
    assert skills["pdf"].description == "from claude.ai"


def test_a_written_skill_beats_the_synced_one(tmp_path):
    home = tmp_path / "home"
    skills_root = home / ".claude" / "skills"
    _write_skill(skills_root / "synced" / "bucket-id" / "pdf", "pdf", "from claude.ai")
    _write_skill(skills_root / "pdf", "pdf", "mine")
    skills = _scan_home_skills(home, tmp_path)
    assert skills["pdf"].description == "mine"


def test_synced_dot_directories_are_skipped(tmp_path):
    "Claude keeps .staging and .trash beside the buckets."
    home = tmp_path / "home"
    synced = home / ".claude" / "skills" / "synced"
    _write_skill(synced / ".trash" / "pdf", "pdf", "trashed")
    skills = _scan_home_skills(home, tmp_path)
    assert "pdf" not in skills


def test_installed_plugin_skills_are_scanned(tmp_path):
    home = tmp_path / "home"
    plugins_root = home / ".claude" / "plugins"
    installed = plugins_root / "cache" / "market" / "documents" / "abc123"
    _write_skill(installed / "skills" / "pdf", "pdf", "from a plugin")
    plugins_root.mkdir(parents=True, exist_ok=True)
    (plugins_root / "installed_plugins.json").write_text(
        json.dumps(
            {
                "version": 2,
                "plugins": {"documents@market": [{"installPath": str(installed)}]},
            }
        ),
        encoding="utf-8",
    )
    skills = _scan_home_skills(home, tmp_path)
    assert skills["pdf"].description == "from a plugin"


def test_marketplace_plugin_skills_are_scanned(tmp_path):
    "A marketplace keeps its plugins in plugins/<name>/, not at its own root."
    home = tmp_path / "home"
    plugin = (
        home / ".claude" / "plugins" / "marketplaces" / "acme" / "plugins" / "documents"
    )
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
    _write_skill(plugin / "skills" / "pdf", "pdf", "from a marketplace")
    skills = _scan_home_skills(home, tmp_path)
    assert skills["pdf"].description == "from a marketplace"
