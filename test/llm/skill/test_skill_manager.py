import os
import shutil
from pathlib import Path

import pytest

from zrb.llm.skill.manager import SkillManager


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

    yield project_dir

    if original_home:
        os.environ["HOME"] = original_home
    else:
        del os.environ["HOME"]


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
