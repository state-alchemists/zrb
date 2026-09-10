from unittest.mock import patch

import pytest

from zrb.llm.skill.manager import Skill, SkillManager
from zrb.llm.skill.manager import skill_manager as skill_manager_singleton


@pytest.fixture
def skill_manager(tmp_path):
    return SkillManager(root_dir=str(tmp_path))


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


def test_skill_explicit_fields():
    skill = Skill(
        name="s",
        path="p",
        description="d",
        model_invocable=False,
        user_invocable=False,
        argument_hint="[x]",
        allowed_tools=["Read"],
        model="gpt-4",
        context="fork",
        agent="Explore",
        content="body",
        companion_files=["a.txt"],
    )
    assert skill.model_invocable is False
    assert skill.user_invocable is False
    assert skill.argument_hint == "[x]"
    assert skill.allowed_tools == ["Read"]
    assert skill.model == "gpt-4"
    assert skill.context == "fork"
    assert skill.agent == "Explore"
    assert skill.content == "body"
    assert skill.companion_files == ["a.txt"]


def test_module_singleton_is_skill_manager():
    assert isinstance(skill_manager_singleton, SkillManager)


def test_get_skills_scans_lazily(tmp_path):
    skill_dir = tmp_path / "lazy"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Lazy Skill")
    manager = SkillManager(root_dir=str(tmp_path), search_dirs=[tmp_path])
    # No explicit scan() called -> get_skills triggers it.
    names = [s.name for s in manager.get_skills()]
    assert "Lazy Skill" in names


def test_add_skill_then_get_skill(manager):
    manager.scan(search_dirs=[])
    skill = Skill(name="added", path="p", description="d")
    manager.add_skill(skill)
    assert manager.get_skill("added") is skill


def test_get_skill_returns_none_for_unknown(manager):
    manager.scan(search_dirs=[])
    assert manager.get_skill("nope") is None


def test_get_skill_partial_path_match(manager):
    manager.scan(search_dirs=[])
    skill = Skill(name="named", path="/some/path.md", description="d")
    manager.add_skill(skill)
    assert manager.get_skill("/some/path.md") is skill


def test_reload_picks_up_new_files(tmp_path):
    manager = SkillManager(root_dir=str(tmp_path), search_dirs=[tmp_path])
    manager.scan()
    (tmp_path / "fresh.skill.md").write_text("# Fresh")
    assert manager.get_skill("Fresh") is None
    manager.reload()
    assert manager.get_skill("Fresh") is not None


def test_get_skill_content_none_for_unknown(manager):
    manager.scan(search_dirs=[])
    assert manager.get_skill_content("nope") is None


def test_get_skill_content_prefers_content(manager):
    manager.scan(search_dirs=[])
    manager.add_skill(Skill(name="c", path="p", description="d", content="inline"))
    assert manager.get_skill_content("c") == "inline"


def test_get_skill_content_factory(manager):
    manager.scan(search_dirs=[])
    manager.add_skill(
        Skill(
            name="f",
            path="p",
            description="d",
            content_factory=lambda: "made",
        )
    )
    assert manager.get_skill_content("f") == "made"


def test_get_skill_content_factory_error(manager):
    manager.scan(search_dirs=[])

    def boom():
        raise RuntimeError("kaboom")

    manager.add_skill(Skill(name="f", path="p", description="d", content_factory=boom))
    result = manager.get_skill_content("f")
    assert "Error executing skill factory" in result
    assert "kaboom" in result


def test_get_skill_content_reads_file(manager, tmp_path):
    manager.scan(search_dirs=[])
    skill_file = tmp_path / "real.md"
    skill_file.write_text("on-disk content")
    manager.add_skill(Skill(name="r", path=str(skill_file), description="d"))
    assert manager.get_skill_content("r") == "on-disk content"


def test_get_skill_content_file_read_error(manager):
    manager.scan(search_dirs=[])
    manager.add_skill(Skill(name="r", path="/no/such/file.md", description="d"))
    assert "Error reading skill file" in manager.get_skill_content("r")


def test_scan_markdown_frontmatter_full(manager, tmp_path):
    (tmp_path / "SKILL.md").write_text(
        """---
name: Custom
description: A description
argument-hint: "[arg]"
allowed-tools: Read, Grep
model: gpt-4
context: fork
agent: Explore
disable-model-invocation: true
user-invocable: false
---
# Ignored
""",
        encoding="utf-8",
    )
    manager.scan(search_dirs=[tmp_path])
    skill = manager.get_skill("Custom")
    assert skill.description == "A description"
    assert skill.argument_hint == "[arg]"
    assert skill.allowed_tools == ["Read", "Grep"]
    assert skill.model == "gpt-4"
    assert skill.context == "fork"
    assert skill.agent == "Explore"
    assert skill.model_invocable is False
    assert skill.user_invocable is False


def test_scan_markdown_allowed_tools_as_list(manager, tmp_path):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: lt\nallowed-tools: [A, B]\n---\n",
        encoding="utf-8",
    )
    manager.scan(search_dirs=[tmp_path])
    assert manager.get_skill("lt").allowed_tools == ["A", "B"]


def test_scan_markdown_h1_fallback_name(manager, tmp_path):
    (tmp_path / "SKILL.md").write_text("# H1 Name\nbody")
    manager.scan(search_dirs=[tmp_path])
    assert manager.get_skill("H1 Name") is not None


def test_scan_markdown_no_name_uses_dir_name(manager, tmp_path):
    sub = tmp_path / "dir-name-skill"
    sub.mkdir()
    (sub / "SKILL.md").write_text("just body, no header and no frontmatter")
    manager.scan(search_dirs=[tmp_path])
    assert manager.get_skill("dir-name-skill") is not None


def test_scan_markdown_invalid_frontmatter_logged(manager, tmp_path):
    # Malformed YAML in frontmatter should be caught and logged, not raised.
    (tmp_path / "SKILL.md").write_text("---\nname: [unclosed\n---\n# Heading Name\n")
    # Should not raise.
    manager.scan(search_dirs=[tmp_path])


def test_scan_markdown_hooks_claude_dict_format(manager, tmp_path):
    (tmp_path / "SKILL.md").write_text(
        """---
name: hooked
hooks:
  PreToolUse:
    - matcher: Read
      hooks:
        - type: command
          command: echo hi
---
# body
""",
        encoding="utf-8",
    )
    with patch("zrb.llm.skill.manager.hook_manager") as mock_hooks:
        manager.scan(search_dirs=[tmp_path])
        mock_hooks.parse_claude_format.assert_called_once()


def test_scan_markdown_hooks_zrb_list_format(manager, tmp_path):
    (tmp_path / "SKILL.md").write_text(
        """---
name: hooked
hooks:
  - event: PreToolUse
    command: echo hi
---
# body
""",
        encoding="utf-8",
    )
    with patch("zrb.llm.skill.manager.hook_manager") as mock_hooks:
        manager.scan(search_dirs=[tmp_path])
        mock_hooks.parse_and_register.assert_called_once()


def test_scan_markdown_read_error_logged(manager, tmp_path):
    (tmp_path / "SKILL.md").write_text("# Ok")
    with patch("builtins.open", side_effect=OSError("boom")):
        # Read failure is swallowed and logged.
        manager.scan(search_dirs=[tmp_path])
    # Nothing crashed; no skill loaded.
    assert manager.get_skill("Ok") is None


def test_scan_python_skill_variable(manager, tmp_path):
    (tmp_path / "x.skill.py").write_text(
        "from zrb.llm.skill.manager import Skill\n"
        "skill = Skill(name='pyvar', path=__file__, description='d')\n"
    )
    manager.scan(search_dirs=[tmp_path])
    assert manager.get_skill("pyvar") is not None


def test_scan_python_skill_uppercase_variable(manager, tmp_path):
    (tmp_path / "x.skill.py").write_text(
        "from zrb.llm.skill.manager import Skill\n"
        "SKILL = Skill(name='pyupper', path=__file__, description='d')\n"
    )
    manager.scan(search_dirs=[tmp_path])
    assert manager.get_skill("pyupper") is not None


def test_scan_python_skill_factory(manager, tmp_path):
    (tmp_path / "x.skill.py").write_text(
        "from zrb.llm.skill.manager import Skill\n"
        "def get_skill():\n"
        "    return Skill(name='pyfact', path=__file__, description='d')\n"
    )
    manager.scan(search_dirs=[tmp_path])
    assert manager.get_skill("pyfact") is not None


def test_scan_python_no_skill_object(manager, tmp_path):
    (tmp_path / "x.skill.py").write_text("value = 42\n")
    skills = manager.scan(search_dirs=[tmp_path])
    assert all(s.name != "value" for s in skills)


def test_scan_python_load_error_logged(manager, tmp_path):
    (tmp_path / "x.skill.py").write_text("this is = invalid python !!!")
    # Import failure is swallowed and logged.
    skills = manager.scan(search_dirs=[tmp_path])
    assert isinstance(skills, list)


def test_scan_python_factory_raises_logged(manager, tmp_path):
    # The module loads fine, but get_skill() raises at call time.
    (tmp_path / "x.skill.py").write_text(
        "def get_skill():\n    raise RuntimeError('boom')\n"
    )
    # Exception is swallowed and logged, not raised.
    skills = manager.scan(search_dirs=[tmp_path])
    assert isinstance(skills, list)


def test_scan_dir_permission_error_swallowed(manager, tmp_path):
    with patch("pathlib.Path.iterdir", side_effect=PermissionError):
        skills = manager.scan(search_dirs=[tmp_path])
    assert skills == []


def test_scan_dir_scan_failure_logged(manager, tmp_path):
    # A failure inside scan_files is caught and logged, returning no skills.
    with patch("zrb.llm.skill.manager.scan_files", side_effect=OSError("disk error")):
        skills = manager.scan(search_dirs=[tmp_path])
    assert skills == []


def test_max_depth_limits_recursion(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    shallow = project / "a"
    shallow.mkdir()
    (shallow / "SKILL.md").write_text("# Shallow")
    deep = project
    for i in range(6):
        deep = deep / f"d{i}"
        deep.mkdir()
    (deep / "SKILL.md").write_text("# Deep")

    manager = SkillManager(root_dir=str(project), max_depth=3)
    names = [s.name for s in manager.scan()]
    assert "Shallow" in names
    assert "Deep" not in names


def test_ignore_dirs_skipped(manager, tmp_path):
    ignored = tmp_path / "node_modules"
    ignored.mkdir()
    (ignored / "SKILL.md").write_text("# Hidden")
    skills = manager.scan(search_dirs=[tmp_path])
    assert all(s.name != "Hidden" for s in skills)


def test_search_dirs_property_override_and_default(tmp_path):
    """`search_dirs` returns the explicit override when set, else the
    computed defaults (R7 — the deleted `get_search_directories()` used to
    be the only way to reach the latter)."""
    manager = SkillManager()
    assert manager.search_dirs != []  # computed defaults, non-empty

    manager.search_dirs = [str(tmp_path)]
    assert manager.search_dirs == [str(tmp_path)]

    manager.search_dirs = None  # falls back to computed defaults again
    assert manager.search_dirs != [str(tmp_path)]


def test_search_dirs_setter_invalidates_a_completed_scan(tmp_path):
    skill_dir = tmp_path / "new-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# New Skill\nDescription")

    manager = SkillManager(search_dirs=[])
    assert manager.get_skills() == []  # scanned with no dirs to look in

    manager.search_dirs = [str(tmp_path)]  # reassigning must trigger a rescan
    assert any(s.name == "New Skill" for s in manager.get_skills())


def test_get_search_directories_home(tmp_path):
    home = tmp_path / "home"
    (home / ".claude" / "skills").mkdir(parents=True)
    manager = SkillManager(root_dir=str(tmp_path))
    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        _mock_cfg(mock_cfg, LLM_SEARCH_HOME=True)
        with patch("zrb.llm.skill.manager.Path.home", return_value=home):
            dirs = [str(d).replace("\\", "/") for d in manager.search_dirs]
    assert any(d.endswith("home/.claude/skills") for d in dirs)


def test_get_search_directories_project(tmp_path):
    root = tmp_path / "root"
    leaf = root / "leaf"
    leaf.mkdir(parents=True)
    (root / ".zrb" / "skills").mkdir(parents=True)
    manager = SkillManager(root_dir=str(leaf))
    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        _mock_cfg(mock_cfg, LLM_SEARCH_PROJECT=True)
        dirs = [str(d).replace("\\", "/") for d in manager.search_dirs]
    assert any(d.endswith("root/.zrb/skills") for d in dirs)


def test_get_search_directories_base_dirs(tmp_path):
    base = tmp_path / "base"
    (base / "skills").mkdir(parents=True)
    manager = SkillManager(root_dir=str(tmp_path))
    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        _mock_cfg(mock_cfg, LLM_BASE_SEARCH_DIRS=[str(base)])
        dirs = [str(d).replace("\\", "/") for d in manager.search_dirs]
    assert any(d.endswith("base/skills") for d in dirs)


def test_get_search_directories_extra_skill_dirs(tmp_path):
    extra = tmp_path / "extra"
    extra.mkdir()
    manager = SkillManager(root_dir=str(tmp_path))
    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        _mock_cfg(mock_cfg, LLM_EXTRA_SKILL_DIRS=[str(extra)])
        dirs = [str(d) for d in manager.search_dirs]
    assert any(str(extra) == str(d) for d in dirs)


def test_get_search_directories_plugin_dirs(tmp_path):
    plugin_root = tmp_path / "plugins"
    plugin = plugin_root / "p1"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text('{"name": "p1"}')
    (plugin / "skills").mkdir(parents=True)
    manager = SkillManager(root_dir=str(tmp_path))
    with patch("zrb.llm.skill.manager.CFG") as mock_cfg:
        _mock_cfg(mock_cfg, LLM_PLUGIN_DIRS=[str(plugin_root)])
        dirs = [str(d).replace("\\", "/") for d in manager.search_dirs]
    assert any(d.endswith("p1/skills") for d in dirs)
