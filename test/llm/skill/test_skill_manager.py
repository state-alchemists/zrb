import os
from pathlib import Path
from unittest.mock import patch

import pytest

from zrb.llm.skill.manager import Skill, SkillManager


@pytest.fixture
def temp_skill_env(tmp_path):
    # Setup global skills: ~/.claude/skills/global-skill/SKILL.md
    global_dir = tmp_path / "home" / ".claude" / "skills"
    global_dir.mkdir(parents=True)
    global_skill_dir = global_dir / "global-skill"
    global_skill_dir.mkdir()
    global_skill_file = global_skill_dir / "SKILL.md"
    global_skill_file.write_text(
        """---
name: global-skill
description: A global skill
---
# Global Skill Content
""",
        encoding="utf-8",
    )

    # Setup project skills: project/.claude/skills/project-skill/SKILL.md
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_skill_dir = project_dir / ".claude" / "skills" / "project-skill"
    project_skill_dir.mkdir(parents=True)
    project_skill_file = project_skill_dir / "SKILL.md"
    project_skill_file.write_text(
        """---
name: project-skill
description: A project skill
---
# Project Skill Content
""",
        encoding="utf-8",
    )

    # Setup legacy/fallback skill: project/legacy-skill.skill.md
    legacy_skill_file = project_dir / "legacy-skill.skill.md"
    legacy_skill_file.write_text(
        """# Legacy Skill
Legacy content
""",
        encoding="utf-8",
    )

    # Mock Path.home() and current directory for SkillManager
    original_home = os.environ.get("HOME")
    os.environ["HOME"] = str(tmp_path / "home")

    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        mock_cfg.ROOT_GROUP_NAME = "zrb"
        mock_cfg.LLM_SEARCH_HOME = True
        mock_cfg.LLM_SEARCH_UPWARD = True
        mock_cfg.LLM_UPWARD_ROOT_PATTERNS = [".claude", ".zrb"]
        mock_cfg.LLM_PLUGIN_DIRS = []
        mock_cfg.LLM_ROOT_DIRS = []
        mock_cfg.LLM_SKILL_DIRS = []

        yield project_dir

    if original_home:
        os.environ["HOME"] = original_home
    else:
        del os.environ["HOME"]


@pytest.fixture
def skill_manager(tmp_path):
    return SkillManager(root_dir=str(tmp_path))


# --- Scanning & Precedence Tests ---


def test_skill_manager_scan(temp_skill_env):
    manager = SkillManager(root_dir=str(temp_skill_env))
    skills = manager.scan()

    skill_names = [s.name for s in skills]
    assert "global-skill" in skill_names
    assert "project-skill" in skill_names
    assert "Legacy Skill" in skill_names

    # Check descriptions
    global_skill = next(s for s in skills if s.name == "global-skill")
    assert global_skill.description == "A global skill"

    project_skill = next(s for s in skills if s.name == "project-skill")
    assert project_skill.description == "A project skill"

    legacy_skill = next(s for s in skills if s.name == "Legacy Skill")
    assert legacy_skill.description == "No description"


def test_skill_manager_precedence(temp_skill_env):
    # Create a skill in project that overrides a global one
    override_dir = temp_skill_env / ".claude" / "skills" / "global-skill"
    override_dir.mkdir(parents=True, exist_ok=True)
    override_file = override_dir / "SKILL.md"
    override_file.write_text(
        """---
name: global-skill
description: Overridden description
---
Overridden content
""",
        encoding="utf-8",
    )

    manager = SkillManager(root_dir=str(temp_skill_env))
    skills = manager.scan()

    global_skill = next(s for s in skills if s.name == "global-skill")
    assert global_skill.description == "Overridden description"
    assert "Overridden content" in manager.get_skill_content("global-skill")


# --- Management Tests ---


def test_skill_manager_reload(tmp_path):
    manager = SkillManager(root_dir=str(tmp_path))
    manager.scan()

    # Add a new skill file
    new_skill_file = tmp_path / "new.skill.md"
    new_skill_file.write_text("# New Skill")

    # Should not be found before reload (since it was already scanned)
    assert manager.get_skill("New Skill") is None

    manager.reload()
    assert manager.get_skill("New Skill") is not None


def test_skill_manager_add_skill(skill_manager):
    skill_manager.scan()
    skill = Skill(name="test-skill", path="test.md", description="test")
    skill_manager.add_skill(skill)
    assert skill_manager.get_skill("test-skill") == skill


def test_skill_manager_get_skill_partial_match(skill_manager):
    skill_manager.scan()
    skill = Skill(
        name="my-long-skill-name", path="/path/to/skill.md", description="test"
    )
    skill_manager.add_skill(skill)
    assert skill_manager.get_skill("my-long-skill-name") == skill
    assert skill_manager.get_skill("/path/to/skill.md") == skill
    assert skill_manager.get_skill("non-existent") is None


# --- Content Retrieval Tests ---


def test_skill_manager_get_skill_content_factory(skill_manager):
    skill_manager.scan()
    skill = Skill(
        name="factory-skill",
        path="factory.md",
        description="test",
        content_factory=lambda: "dynamic content",
    )
    skill_manager.add_skill(skill)
    assert skill_manager.get_skill_content("factory-skill") == "dynamic content"


def test_skill_manager_get_skill_content_string(skill_manager):
    skill_manager.scan()
    skill = Skill(
        name="string-skill",
        path="string.md",
        description="test",
        content="static content",
    )
    skill_manager.add_skill(skill)
    assert skill_manager.get_skill_content("string-skill") == "static content"


def test_skill_manager_get_skill_content_file(skill_manager, tmp_path):
    skill_manager.scan()
    skill_file = tmp_path / "file.md"
    skill_file.write_text("file content")
    skill = Skill(name="file-skill", path=str(skill_file), description="test")
    skill_manager.add_skill(skill)
    assert skill_manager.get_skill_content("file-skill") == "file content"


def test_skill_manager_get_skill_content_error(skill_manager):
    skill_manager.scan()
    skill = Skill(name="error-skill", path="/non/existent/path.md", description="test")
    skill_manager.add_skill(skill)
    assert "Error reading skill file" in skill_manager.get_skill_content("error-skill")


# --- File Format & Scanning Logic ---


def test_skill_manager_scan_markdown_h1_fallback(skill_manager, tmp_path):
    skill_dir = tmp_path / "h1-skill"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("# My H1 Skill\nSome description")

    skills = skill_manager.scan(search_dirs=[tmp_path])
    assert any(s.name == "My H1 Skill" for s in skills)


def test_skill_manager_scan_markdown_frontmatter(skill_manager, tmp_path):
    skill_dir = tmp_path / "fm-skill"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("""---
name: Custom Name
description: Custom Description
argument-hint: "[arg]"
allowed-tools: Tool1, Tool2
model: gpt-4
context: fork
agent: Architect
---
# Ignored Header
""")

    skills = skill_manager.scan(search_dirs=[tmp_path])
    skill = skill_manager.get_skill("Custom Name")
    assert skill is not None
    assert skill.description == "Custom Description"
    assert skill.argument_hint == "[arg]"
    assert skill.allowed_tools == ["Tool1", "Tool2"]
    assert skill.model == "gpt-4"
    assert skill.context == "fork"
    assert skill.agent == "Architect"


def test_skill_manager_scan_markdown_allowed_tools_list(skill_manager, tmp_path):
    skill_file = tmp_path / "SKILL.md"
    skill_file.write_text("""---
name: list-tools
allowed-tools: [T1, T2]
---
""")
    skill_manager.scan(search_dirs=[tmp_path])
    skill = skill_manager.get_skill("list-tools")
    assert skill.allowed_tools == ["T1", "T2"]


def test_skill_manager_scan_python_variable(skill_manager, tmp_path):
    skill_file = tmp_path / "test.skill.py"
    skill_file.write_text("""
from zrb.llm.skill.manager import Skill
skill = Skill(name="py-skill", path=__file__, description="py desc")
""")

    skills = skill_manager.scan(search_dirs=[tmp_path])
    assert any(s.name == "py-skill" for s in skills)


def test_skill_manager_scan_python_factory(skill_manager, tmp_path):
    skill_file = tmp_path / "factory.skill.py"
    skill_file.write_text("""
from zrb.llm.skill.manager import Skill
def get_skill():
    return Skill(name="factory-py-skill", path=__file__, description="factory py desc")
""")

    skills = skill_manager.scan(search_dirs=[tmp_path])
    assert any(s.name == "factory-py-skill" for s in skills)


def test_skill_manager_scan_python_no_skill_obj(skill_manager, tmp_path):
    skill_file = tmp_path / "test.skill.py"
    skill_file.write_text("x = 1")
    skills = skill_manager.scan(search_dirs=[tmp_path])
    assert len(skills) == 0


# --- Directory Logic Tests ---


def test_skill_manager_max_depth(tmp_path):
    project_dir = tmp_path / "project_depth"
    project_dir.mkdir()

    # Create skill at depth 1 (relative to project_dir)
    d1 = project_dir / "d1"
    d1.mkdir()
    (d1 / "SKILL.md").write_text("# Skill 1")

    # Create skill at depth 6 (relative to project_dir)
    # project_depth/dir1/dir2/dir3/dir4/dir5/dir6/SKILL.md
    curr = project_dir
    for i in range(1, 7):
        curr = curr / f"dir{i}"
        curr.mkdir()
    (curr / "SKILL.md").write_text("# Deep Skill")

    # Test with max_depth=5
    manager = SkillManager(root_dir=str(project_dir), max_depth=5)
    skills = manager.scan()
    skill_names = [s.name for s in skills]

    assert "Skill 1" in skill_names
    assert "Deep Skill" not in skill_names

    # Test with max_depth=10
    manager = SkillManager(root_dir=str(project_dir), max_depth=10)
    skills = manager.scan()
    skill_names = [s.name for s in skills]
    assert "Deep Skill" in skill_names


def test_skill_manager_ignore_dirs(skill_manager, tmp_path):
    ignore_dir = tmp_path / "node_modules"
    ignore_dir.mkdir()
    skill_file = ignore_dir / "SKILL.md"
    skill_file.write_text("# Ignored Skill")

    skills = skill_manager.scan(search_dirs=[tmp_path])
    assert not any(s.name == "Ignored Skill" for s in skills)


def test_skill_manager_get_search_directories_project_hierarchy(tmp_path):
    # Setup a nested directory structure
    root = tmp_path / "root"
    mid = root / "mid"
    leaf = mid / "leaf"
    leaf.mkdir(parents=True)

    (root / ".zrb" / "skills").mkdir(parents=True)
    (mid / ".claude" / "skills").mkdir(parents=True)
    (leaf / ".zrb" / "skills").mkdir(parents=True)

    manager = SkillManager(root_dir=str(leaf))
    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        mock_cfg.ROOT_GROUP_NAME = "zrb"
        mock_cfg.LLM_SEARCH_HOME = True
        mock_cfg.LLM_SEARCH_UPWARD = True
        mock_cfg.LLM_UPWARD_ROOT_PATTERNS = [".claude", ".zrb"]
        dirs = [str(d) for d in manager.get_search_directories()]
        assert any("root/.zrb/skills" in d for d in dirs)
        assert any("mid/.claude/skills" in d for d in dirs)
        assert any("leaf/.zrb/skills" in d for d in dirs)


def test_skill_manager_get_search_directories_plugins(skill_manager, tmp_path):
    # Test with direct skill directories (LLM_SKILL_DIRS)
    skill_dir = tmp_path / "my_skills"
    (skill_dir / "test-skill").mkdir(parents=True)
    (skill_dir / "test-skill" / "SKILL.md").write_text("# Test Skill")

    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        mock_cfg.ROOT_GROUP_NAME = "zrb"
        mock_cfg.LLM_SEARCH_HOME = True
        mock_cfg.LLM_SEARCH_UPWARD = True
        mock_cfg.LLM_UPWARD_ROOT_PATTERNS = [".claude", ".zrb"]
        mock_cfg.LLM_SKILL_DIRS = [str(skill_dir)]
        dirs = skill_manager.get_search_directories()
        assert any(str(skill_dir) == str(d) for d in dirs)


def test_skill_manager_get_search_directories_with_plugins(skill_manager, tmp_path):
    # Test with proper plugin structure (with manifest)
    plugin_root = tmp_path / "plugins"
    plugin_dir = plugin_root / "my-plugin"
    (plugin_dir / ".claude-plugin").mkdir(parents=True)
    (plugin_dir / ".claude-plugin" / "plugin.json").write_text('{"name": "my-plugin"}')
    (plugin_dir / "skills" / "plugin-skill").mkdir(parents=True)
    (plugin_dir / "skills" / "plugin-skill" / "SKILL.md").write_text("# Plugin Skill")

    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        mock_cfg.ROOT_GROUP_NAME = "zrb"
        mock_cfg.LLM_SEARCH_HOME = True
        mock_cfg.LLM_SEARCH_UPWARD = True
        mock_cfg.LLM_UPWARD_ROOT_PATTERNS = [".claude", ".zrb"]
        mock_cfg.LLM_PLUGIN_DIRS = [str(plugin_root)]
        dirs = skill_manager.get_search_directories()
        # Should find skills inside plugins
        assert any("my-plugin/skills" in str(d) for d in dirs)


def test_skill_manager_scan_permission_error(skill_manager, tmp_path):
    with patch("pathlib.Path.iterdir", side_effect=PermissionError):
        skills = skill_manager.scan(search_dirs=[tmp_path])
        assert len(skills) == 0
