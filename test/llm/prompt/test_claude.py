from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.prompt.claude import (
    create_claude_skills_prompt,
    create_project_context_prompt,
)
from zrb.llm.skill.manager import Skill, SkillManager

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


def test_create_project_context_prompt_with_agents_md(tmp_path):
    """AGENTS.md content is included in the returned prompt."""
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("# Test Agents\nSome agent guidance here.")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[tmp_path]
    ):
        result = handler(ctx, "base prompt", _identity_next)

    assert "Test Agents" in result


def test_create_project_context_prompt_with_claude_md(tmp_path):
    """CLAUDE.md content is included in the returned prompt."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("Claude instructions content")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[tmp_path]
    ):
        result = handler(ctx, "base prompt", _identity_next)

    assert "Claude instructions content" in result


def test_create_project_context_prompt_with_empty_doc_file(tmp_path):
    """An empty file is listed in All Documentation Files but not loaded."""
    readme = tmp_path / "README.md"
    readme.write_text("")  # empty

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[tmp_path]
    ):
        result = handler(ctx, "base prompt", _identity_next)

    # File is listed (exists) but no content is loaded
    assert "README.md" in result


def test_create_project_context_prompt_multiple_dirs(tmp_path):
    """The most-specific (last) directory's content takes precedence."""
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    (dir1 / "AGENTS.md").write_text("Content from dir1")

    dir2 = tmp_path / "dir2"
    dir2.mkdir()
    (dir2 / "AGENTS.md").write_text("Content from dir2 - more specific")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[dir1, dir2]
    ):
        result = handler(ctx, "base prompt", _identity_next)

    # Most-specific (dir2) content must appear
    assert "more specific" in result


def test_create_project_context_prompt_truncates_large_content(tmp_path):
    """Content exceeding MAX_PROJECT_DOC_CHARS (8000) is truncated."""
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("A" * 10000)

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[tmp_path]
    ):
        result = handler(ctx, "base prompt", _identity_next)

    # Some content must appear
    assert "A" * 100 in result
    # But not all 10000 chars of 'A' in a single run beyond the limit
    assert "A" * 9000 not in result


def test_create_project_context_prompt_listed_files_section(tmp_path):
    """Files appear in the 'All Documentation Files' section."""
    (tmp_path / "AGENTS.md").write_text("Agent content")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[tmp_path]
    ):
        result = handler(ctx, "base prompt", _identity_next)

    assert "All Documentation Files" in result


def test_create_project_context_prompt_all_four_doc_types(tmp_path):
    """All four recognised doc filenames are picked up when present."""
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


def test_create_project_context_prompt_unreadable_file(tmp_path):
    """Unreadable files are silently skipped (handled by _load_file_content)."""
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("readable content")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    # Simulate open() raising an exception for that file
    original_open = open

    def patched_open(path, *args, **kwargs):
        if str(path) == str(agents_md):
            raise PermissionError("no access")
        return original_open(path, *args, **kwargs)

    with patch(
        "zrb.llm.prompt.claude._get_search_directories", return_value=[tmp_path]
    ):
        with patch("builtins.open", side_effect=patched_open):
            result = handler(ctx, "base prompt", _identity_next)

    # File is listed but not loaded; no crash
    assert "AGENTS.md" in result


# ---------------------------------------------------------------------------
# create_claude_skills_prompt tests
# ---------------------------------------------------------------------------


def test_create_claude_skills_prompt_no_skills(tmp_path):
    """Empty skill manager: next_handler is still called."""
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[])  # no skills

    handler = create_claude_skills_prompt(sm)
    ctx = _make_ctx()
    captured = []

    def capture_next(c, p):
        captured.append(p)
        return p

    result = handler(ctx, "base prompt", capture_next)

    assert captured  # next_handler was called
    assert result is not None


def test_create_claude_skills_prompt_with_skills(tmp_path):
    """Skills found by the manager appear in the returned prompt."""
    skill_file = tmp_path / "test.skill.md"
    skill_file.write_text(
        "---\nname: test-skill\ndescription: A test skill\n---\n# Content"
    )
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[tmp_path])

    handler = create_claude_skills_prompt(sm)
    ctx = _make_ctx()

    result = handler(ctx, "base prompt", _identity_next)

    assert "test-skill" in result


def test_create_claude_skills_prompt_with_active_skills(tmp_path):
    """Active skills are fully loaded and listed under 'Active Skills'."""
    skill_file = tmp_path / "active.skill.md"
    skill_file.write_text(
        "---\nname: active-skill\ndescription: Active skill\n---\nSkill content here"
    )
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[tmp_path])

    handler = create_claude_skills_prompt(sm, active_skills=["active-skill"])
    ctx = _make_ctx()

    result = handler(ctx, "base prompt", _identity_next)

    assert "active-skill" in result
    assert "Active Skills" in result


def test_create_claude_skills_prompt_active_skill_content_loaded(tmp_path):
    """Full content of an active skill is embedded in the prompt."""
    skill_file = tmp_path / "deep.skill.md"
    skill_file.write_text(
        "---\nname: deep-skill\ndescription: Deep skill\n---\nDeep skill body text"
    )
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[tmp_path])

    handler = create_claude_skills_prompt(sm, active_skills=["deep-skill"])
    ctx = _make_ctx()

    result = handler(ctx, "base prompt", _identity_next)

    assert "Deep skill body text" in result


def test_create_claude_skills_prompt_include_claude_skills_false(tmp_path):
    """include_claude_skills=False filters out non-core_mandate skills."""
    skill_file = tmp_path / "ordinary.skill.md"
    skill_file.write_text(
        "---\nname: ordinary-skill\ndescription: Ordinary skill\n---\nContent"
    )
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[tmp_path])

    handler = create_claude_skills_prompt(
        sm, active_skills=["ordinary-skill"], include_claude_skills=False
    )
    ctx = _make_ctx()

    result = handler(ctx, "base prompt", _identity_next)

    # ordinary-skill is not a core_mandate_ skill so its content should NOT
    # appear in the active section (may still appear in Available Skills section)
    assert (
        "ordinary-skill" not in result.split("Active Skills")[1]
        if "Active Skills" in result
        else True
    )


def test_create_claude_skills_prompt_active_skill_missing(tmp_path):
    """Requesting a non-existent active skill does not crash."""
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[tmp_path])

    handler = create_claude_skills_prompt(sm, active_skills=["nonexistent-skill"])
    ctx = _make_ctx()

    # Should not raise
    result = handler(ctx, "base prompt", _identity_next)
    assert result is not None


def test_create_claude_skills_prompt_calls_next_handler(tmp_path):
    """next_handler is always called exactly once."""
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[])

    handler = create_claude_skills_prompt(sm)
    ctx = _make_ctx()
    calls = []

    def counting_next(c, p):
        calls.append(p)
        return p

    handler(ctx, "base prompt", counting_next)

    assert len(calls) == 1


def test_create_claude_skills_prompt_base_prompt_preserved(tmp_path):
    """Base prompt text is always included in the forwarded prompt."""
    sm = SkillManager(root_dir=str(tmp_path))
    sm.scan(search_dirs=[])

    handler = create_claude_skills_prompt(sm)
    ctx = _make_ctx()

    result = handler(ctx, "unique-base-content", _identity_next)

    assert "unique-base-content" in result


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
