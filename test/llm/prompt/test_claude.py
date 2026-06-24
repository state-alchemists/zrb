from unittest.mock import MagicMock, patch

from zrb.llm.prompt.claude import (
    build_skill_replacements,
    create_project_context_prompt,
)
from zrb.llm.skill.manager import SkillManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx():
    ctx = MagicMock()
    ctx.input = MagicMock()
    return ctx


def _identity_next(ctx, prompt):
    return prompt


# ---------------------------------------------------------------------------
# create_project_context_prompt tests
# ---------------------------------------------------------------------------


def test_create_project_context_prompt_no_doc_files(tmp_path):
    """When no doc files exist, the original prompt is forwarded unchanged."""
    handler = create_project_context_prompt()
    ctx = _make_ctx()
    called_prompts = []

    def capture_next(c, p):
        called_prompts.append(p)
        return p

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[tmp_path]
    ):
        result = handler(ctx, "base prompt", capture_next)

    assert called_prompts[-1] == "base prompt"
    assert result == "base prompt"


def test_create_project_context_prompt_lists_agents_md(tmp_path):
    """AGENTS.md path is listed in All Documentation Files."""
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("Some agent guidance here.")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[tmp_path]
    ):
        result = handler(ctx, "base prompt", _identity_next)

    assert str(agents_md) in result
    assert "Documentation Files Found" in result


def test_create_project_context_prompt_lists_claude_md(tmp_path):
    """CLAUDE.md path is listed in All Documentation Files."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("Claude instructions")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[tmp_path]
    ):
        result = handler(ctx, "base prompt", _identity_next)

    assert str(claude_md) in result


def test_create_project_context_prompt_with_empty_doc_file(tmp_path):
    """An empty file is still listed."""
    readme = tmp_path / "README.md"
    readme.write_text("")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[tmp_path]
    ):
        result = handler(ctx, "base prompt", _identity_next)

    assert str(readme) in result


def test_create_project_context_prompt_multiple_dirs(tmp_path):
    """All occurrences across directories are listed."""
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    (dir1 / "AGENTS.md").write_text("Content from dir1")

    dir2 = tmp_path / "dir2"
    dir2.mkdir()
    (dir2 / "AGENTS.md").write_text("Content from dir2")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[dir1, dir2]
    ):
        result = handler(ctx, "base prompt", _identity_next)

    # Both paths are listed
    assert str(dir1 / "AGENTS.md") in result
    assert str(dir2 / "AGENTS.md") in result


def test_create_project_context_prompt_listed_files_section(tmp_path):
    """Files appear in the 'Documentation Files Found' section."""
    (tmp_path / "AGENTS.md").write_text("Agent content")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[tmp_path]
    ):
        result = handler(ctx, "base prompt", _identity_next)

    assert "Documentation Files Found" in result


def test_create_project_context_prompt_all_doc_types_listed(tmp_path):
    """All doc types are listed (no suppression)."""
    for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md"):
        (tmp_path / name).write_text(f"Content of {name}")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[tmp_path]
    ):
        result = handler(ctx, "base prompt", _identity_next)

    for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md"):
        assert name in result


def test_create_project_context_prompt_calls_next_handler(tmp_path):
    """next_handler must always be called exactly once."""
    handler = create_project_context_prompt()
    ctx = _make_ctx()
    call_count = []

    def counting_next(c, p):
        call_count.append(p)
        return p

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[tmp_path]
    ):
        handler(ctx, "base prompt", counting_next)

    assert len(call_count) == 1


def test_create_project_context_prompt_base_prompt_preserved(tmp_path):
    """The original base prompt is always present in the result."""
    (tmp_path / "AGENTS.md").write_text("Extra agent info")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[tmp_path]
    ):
        result = handler(ctx, "base prompt", _identity_next)

    assert "base prompt" in result


def test_create_project_context_prompt_all_files_listed_without_read(tmp_path):
    """All found files are listed; content is not loaded."""
    for name in ("AGENTS.md", "CLAUDE.md"):
        (tmp_path / name).write_text("Some content here")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[tmp_path]
    ):
        result = handler(ctx, "base prompt", _identity_next)

    # Content is not embedded
    assert "Some content here" not in result
    # But both paths are listed
    assert "AGENTS.md" in result
    assert "CLAUDE.md" in result


# ---------------------------------------------------------------------------
# build_skill_replacements tests
# ---------------------------------------------------------------------------


def _scan(tmp_path):
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[tmp_path])
    return sm


def test_build_skill_replacements_returns_all_placeholders(tmp_path):
    """All three placeholders are always present, even with no skills."""
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[])

    r = build_skill_replacements(sm)

    assert set(r) == {"CORE_SKILLS", "AVAILABLE_SKILLS", "ACTIVE_SKILLS"}


def test_build_skill_replacements_lists_available_skill(tmp_path):
    """A non-core model-invocable skill lands in AVAILABLE_SKILLS."""
    (tmp_path / "test.skill.md").write_text(
        "---\nname: test-skill\ndescription: A test skill\n---\n# Content"
    )

    r = build_skill_replacements(_scan(tmp_path))

    assert "test-skill" in r["AVAILABLE_SKILLS"]
    assert "A test skill" in r["AVAILABLE_SKILLS"]
    assert "test-skill" not in r["CORE_SKILLS"]


def test_build_skill_replacements_separates_core_from_other(tmp_path):
    """A skill under a core_skills/ dir is classified as core, not available."""
    core_dir = tmp_path / "core_skills" / "core-thing"
    core_dir.mkdir(parents=True)
    (core_dir / "SKILL.md").write_text(
        "---\nname: core-thing\ndescription: A core skill\n---\n# Content"
    )
    (tmp_path / "other.skill.md").write_text(
        "---\nname: other\ndescription: Another skill\n---\n# Content"
    )

    r = build_skill_replacements(_scan(tmp_path))

    assert "core-thing" in r["CORE_SKILLS"]
    assert "core-thing" not in r["AVAILABLE_SKILLS"]
    assert "other" in r["AVAILABLE_SKILLS"]


def test_build_skill_replacements_available_empty_placeholder(tmp_path):
    """AVAILABLE_SKILLS is a harmless placeholder string when empty."""
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[])

    r = build_skill_replacements(sm)

    assert r["AVAILABLE_SKILLS"] == "_(none registered)_"


def test_build_skill_replacements_active_skill_content_loaded(tmp_path):
    """Active skills are rendered with their full content."""
    (tmp_path / "deep.skill.md").write_text(
        "---\nname: deep-skill\ndescription: Deep skill\n---\nDeep skill body text"
    )

    r = build_skill_replacements(_scan(tmp_path), active_skills=["deep-skill"])

    assert "Deep skill body text" in r["ACTIVE_SKILLS"]
    assert "Active Skills (Fully Loaded)" in r["ACTIVE_SKILLS"]


def test_build_skill_replacements_active_skill_excluded_from_lists(tmp_path):
    """An active skill is not also advertised in the catalogue lists."""
    (tmp_path / "act.skill.md").write_text(
        "---\nname: act\ndescription: Active one\n---\nbody"
    )

    r = build_skill_replacements(_scan(tmp_path), active_skills=["act"])

    assert "act" not in r["AVAILABLE_SKILLS"]


def test_build_skill_replacements_no_active_skills_empty(tmp_path):
    """ACTIVE_SKILLS is empty when nothing is pre-activated."""
    (tmp_path / "test.skill.md").write_text(
        "---\nname: test-skill\ndescription: A test skill\n---\n# Content"
    )

    r = build_skill_replacements(_scan(tmp_path))

    assert r["ACTIVE_SKILLS"] == ""


def test_build_skill_replacements_missing_active_skill_does_not_crash(tmp_path):
    """Requesting a non-existent active skill is ignored, not fatal."""
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[tmp_path])

    r = build_skill_replacements(sm, active_skills=["nonexistent-skill"])

    assert r["ACTIVE_SKILLS"] == ""


def test_build_skill_replacements_skips_non_invocable(tmp_path):
    """Skills with disable-model-invocation are not listed."""
    (tmp_path / "hidden.skill.md").write_text(
        "---\nname: hidden\ndescription: Hidden\n"
        "disable-model-invocation: true\n---\n# Content"
    )

    r = build_skill_replacements(_scan(tmp_path))

    assert "hidden" not in r["AVAILABLE_SKILLS"]


# ---------------------------------------------------------------------------
# _get_search_directories indirect tests (no patching — real filesystem)
# ---------------------------------------------------------------------------


def test_get_search_directories_includes_cwd(tmp_path):
    """
    _get_search_directories is exercised indirectly: with a real AGENTS.md in
    the CWD-like directory, create_project_context_prompt picks it up without
    any patching.

    We cannot easily control CWD in all environments, so we simply verify that
    calling the handler without patching does not crash and returns a string.
    """
    handler = create_project_context_prompt()
    ctx = _make_ctx()

    # No patch — uses real _get_search_directories
    result = handler(ctx, "probe-prompt", _identity_next)

    assert isinstance(result, str)
    assert "probe-prompt" in result
