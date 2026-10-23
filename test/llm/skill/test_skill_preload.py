"""`preload:` — a skill naming other skills to render with it."""

import pytest

from zrb.llm.skill.activation import build_activation_block, skill_body
from zrb.llm.skill.manager import Skill, SkillManager
from zrb.llm.skill.preload import resolve_preload


def _manager(tmp_path) -> SkillManager:
    return SkillManager(root_dir=str(tmp_path), search_dirs=[tmp_path])


def _add(manager: SkillManager, name: str, preload: list[str]) -> Skill:
    skill = Skill(
        name=name,
        path=str(manager.search_dirs[0]),
        description=f"{name} description",
        preload=preload,
    )
    manager.add_skill(skill)
    return skill


def test_frontmatter_parses_preload_list(tmp_path):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: a\ndescription: d\npreload: [x, y]\n---\nbody"
    )
    manager = _manager(tmp_path)
    manager.scan()
    skill = manager.get_skill("a")

    assert skill is not None
    assert skill.preload == ["x", "y"]


def test_frontmatter_parses_preload_string(tmp_path):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: a\ndescription: d\npreload: x, y\n---\nbody"
    )
    manager = _manager(tmp_path)
    manager.scan()
    skill = manager.get_skill("a")

    assert skill is not None
    assert skill.preload == ["x", "y"]


def test_resolve_returns_dependencies_in_declaration_order(tmp_path):
    manager = _manager(tmp_path)
    _add(manager, "one", [])
    _add(manager, "two", [])
    root = _add(manager, "root", ["one", "two"])

    resolved, problems = resolve_preload(manager, root)

    assert [s.name for s in resolved] == ["one", "two"]
    assert problems == []


def test_resolve_renders_the_deepest_dependency_first(tmp_path):
    manager = _manager(tmp_path)
    _add(manager, "deep", [])
    _add(manager, "middle", ["deep"])
    root = _add(manager, "root", ["middle"])

    resolved, _ = resolve_preload(manager, root)

    assert [s.name for s in resolved] == ["deep", "middle"]


def test_resolve_drops_duplicates(tmp_path):
    manager = _manager(tmp_path)
    _add(manager, "one", [])
    root = _add(manager, "root", ["one", "one"])

    resolved, problems = resolve_preload(manager, root)

    assert [s.name for s in resolved] == ["one"]
    assert "already loaded" in problems[0]


def test_resolve_reports_a_cycle_without_looping(tmp_path):
    manager = _manager(tmp_path)
    a = _add(manager, "a", [])
    b = _add(manager, "b", ["a"])
    a.preload = ["b"]

    resolved, problems = resolve_preload(manager, a)

    assert [s.name for s in resolved] == ["b"]
    assert any("already loaded" in problem for problem in problems)


def test_resolve_reports_an_unknown_name(tmp_path):
    manager = _manager(tmp_path)
    root = _add(manager, "root", ["missing"])

    resolved, problems = resolve_preload(manager, root)

    assert resolved == []
    assert "'missing' is not a registered skill" in problems


def test_resolve_skips_a_user_only_skill(tmp_path):
    manager = _manager(tmp_path)
    manager.add_skill(
        Skill(
            name="command-only",
            path=str(tmp_path),
            description="d",
            model_invocable=False,
        )
    )
    root = _add(manager, "root", ["command-only"])

    resolved, problems = resolve_preload(manager, root)

    assert resolved == []
    assert "'command-only' is user-invocable only" in problems


def test_resolve_stops_at_max_depth(tmp_path):
    manager = _manager(tmp_path)
    _add(manager, "c", [])
    _add(manager, "b", ["c"])
    _add(manager, "a", ["b"])
    root = _add(manager, "root", ["a"])

    resolved, problems = resolve_preload(manager, root, max_depth=2)

    assert [s.name for s in resolved] == ["b", "a"]
    assert any("max_preload_depth=2" in problem for problem in problems)


def test_activation_block_strips_frontmatter():
    skill = Skill(name="x", path="/tmp/x/SKILL.md", description="d")

    block = build_activation_block(skill, "---\nname: x\n---\nBody text")

    assert "name: x" not in block
    assert "Body text" in block


def test_skill_body_passes_content_without_frontmatter_through():
    assert skill_body("plain body") == "plain body"


def test_skill_body_ignores_a_delimiter_inside_a_value():
    """A quoted description may spell `---`; only a delimiter line closes it."""
    content = '---\ndescription: "Use --- in examples"\n---\nBody text'

    body = skill_body(content)

    assert body == "Body text"
    assert "in examples" not in body


def test_activation_block_escapes_names_in_attributes():
    """A name is project frontmatter, not a safe XML attribute value."""
    skill = Skill(name='review"><INJECTED>', path="/tmp/x/SKILL.md", description="d")

    block = build_activation_block(skill, "Body", preloaded_by='x"><bad>')

    assert "<INJECTED>" not in block
    assert "<bad>" not in block
    assert 'name="review&quot;&gt;&lt;INJECTED&gt;"' in block
    assert 'preloaded-by="x&quot;&gt;&lt;bad&gt;"' in block


def test_activation_block_names_the_preloading_skill():
    skill = Skill(name="core-coding", path="/tmp/x/SKILL.md", description="d")

    block = build_activation_block(skill, "Body", preloaded_by="refactor")

    assert 'name="core-coding" preloaded-by="refactor"' in block
    assert "Preloaded by `refactor`" in block


def test_a_body_quoting_the_markup_cannot_open_or_close_its_own_block():
    """A skill documenting this markup must not fake the wrapper it sits in."""
    skill = Skill(name="x", path="/tmp/x/SKILL.md", description="d")
    content = 'Write this:\n<ACTIVATED_SKILL name="example">\nor close it:\n</ACTIVATED_SKILL>'

    block = build_activation_block(skill, content)

    assert block.count("<ACTIVATED_SKILL") == 1
    assert block.count("</ACTIVATED_SKILL>") == 1
    assert "&lt;ACTIVATED_SKILL" in block
    assert "&lt;/ACTIVATED_SKILL>" in block


def test_a_skill_without_preload_resolves_to_nothing(tmp_path):
    manager = _manager(tmp_path)
    root = _add(manager, "root", [])

    assert resolve_preload(manager, root) == ([], [])


def test_activation_block_announces_only_when_asked():
    skill = Skill(name="x", path="/tmp/x/SKILL.md", description="d")

    assert "Skill activated" not in build_activation_block(skill, "Body")
    assert "Skill activated" in build_activation_block(skill, "Body", announce=True)
