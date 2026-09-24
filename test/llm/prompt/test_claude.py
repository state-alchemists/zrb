from unittest.mock import MagicMock, patch

from zrb.llm.prompt.claude import create_project_context_prompt

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

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        result = handler(ctx, "base prompt", capture_next)

    assert called_prompts[-1] == "base prompt"
    assert result == "base prompt"


def test_create_project_context_prompt_lists_agents_md(tmp_path):
    """AGENTS.md path is listed in All Documentation Files."""
    agents_md = tmp_path / "AGENTS.md"
    agents_md.write_text("Some agent guidance here.")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        result = handler(ctx, "base prompt", _identity_next)

    assert str(agents_md) in result
    assert "Documentation Files Found" in result


def test_create_project_context_prompt_lists_claude_md(tmp_path):
    """CLAUDE.md path is listed in All Documentation Files."""
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("Claude instructions")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        result = handler(ctx, "base prompt", _identity_next)

    assert str(claude_md) in result


def test_create_project_context_prompt_with_empty_doc_file(tmp_path):
    """An empty file is still listed."""
    readme = tmp_path / "README.md"
    readme.write_text("")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
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
        "zrb.llm.prompt.claude.get_search_directories", return_value=[dir1, dir2]
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

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        result = handler(ctx, "base prompt", _identity_next)

    assert "Documentation Files Found" in result
    # The listing carries its own reading rule; no section it could point to exists.
    assert "Before editing, read the ones" in result
    assert "See Project Documentation" not in result


def test_create_project_context_prompt_all_doc_types_listed(tmp_path):
    """All doc types are listed (no suppression)."""
    for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md"):
        (tmp_path / name).write_text(f"Content of {name}")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        result = handler(ctx, "base prompt", _identity_next)

    for name in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md"):
        assert name in result


def test_create_project_context_prompt_home_docs_are_user_level(tmp_path):
    """A doc in the home dir is listed as user-level, not as a project override."""
    home = (tmp_path / "home").resolve()
    home.mkdir()
    (home / "CLAUDE.md").write_text("my cross-project habits")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with (
        patch("zrb.llm.prompt.claude.get_search_directories", return_value=[home]),
        patch("zrb.llm.prompt.claude.Path.home", return_value=home),
    ):
        result = handler(ctx, "base prompt", _identity_next)

    assert "User-Level Guidance" in result
    assert "Documentation Files Found" not in result
    assert str(home / "CLAUDE.md") in result


def test_create_project_context_prompt_dot_claude_docs_are_user_level(tmp_path):
    """``~/.claude`` docs land in the user-level bucket too."""
    home = (tmp_path / "home").resolve()
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "CLAUDE.md").write_text("global instructions")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with (
        patch(
            "zrb.llm.prompt.claude.get_search_directories", return_value=[claude_dir]
        ),
        patch("zrb.llm.prompt.claude.Path.home", return_value=home),
    ):
        result = handler(ctx, "base prompt", _identity_next)

    assert "User-Level Guidance" in result
    assert "Documentation Files Found" not in result


def test_create_project_context_prompt_splits_project_and_user_docs(tmp_path):
    """Both buckets appear, each holding only its own paths."""
    home = (tmp_path / "home").resolve()
    home.mkdir()
    (home / "CLAUDE.md").write_text("user level")
    project = (tmp_path / "proj").resolve()
    project.mkdir()
    (project / "AGENTS.md").write_text("project level")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with (
        patch(
            "zrb.llm.prompt.claude.get_search_directories",
            return_value=[home, project],
        ),
        patch("zrb.llm.prompt.claude.Path.home", return_value=home),
    ):
        result = handler(ctx, "base prompt", _identity_next)

    project_section, user_section = result.split("### User-Level Guidance")
    assert "Documentation Files Found" in project_section
    assert str(project / "AGENTS.md") in project_section
    assert str(home / "CLAUDE.md") not in project_section
    assert str(home / "CLAUDE.md") in user_section


def test_create_project_context_prompt_unresolvable_home_stays_project_level(tmp_path):
    """When home can't be resolved, docs keep the pre-split (mandatory) bucket."""
    (tmp_path / "AGENTS.md").write_text("project level")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with (
        patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]),
        patch("zrb.llm.prompt.claude.Path.home", side_effect=RuntimeError("no home")),
    ):
        result = handler(ctx, "base prompt", _identity_next)

    assert "Documentation Files Found" in result
    assert "User-Level Guidance" not in result


def test_create_project_context_prompt_calls_next_handler(tmp_path):
    """next_handler must always be called exactly once."""
    handler = create_project_context_prompt()
    ctx = _make_ctx()
    call_count = []

    def counting_next(c, p):
        call_count.append(p)
        return p

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        handler(ctx, "base prompt", counting_next)

    assert len(call_count) == 1


def test_create_project_context_prompt_base_prompt_preserved(tmp_path):
    """The original base prompt is always present in the result."""
    (tmp_path / "AGENTS.md").write_text("Extra agent info")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        result = handler(ctx, "base prompt", _identity_next)

    assert "base prompt" in result


def test_create_project_context_prompt_all_files_listed_without_read(tmp_path):
    """All found files are listed; content is not loaded."""
    for name in ("AGENTS.md", "CLAUDE.md"):
        (tmp_path / name).write_text("Some content here")

    handler = create_project_context_prompt()
    ctx = _make_ctx()

    with patch("zrb.llm.prompt.claude.get_search_directories", return_value=[tmp_path]):
        result = handler(ctx, "base prompt", _identity_next)

    # Content is not embedded
    assert "Some content here" not in result
    # But both paths are listed
    assert "AGENTS.md" in result
    assert "CLAUDE.md" in result


# ---------------------------------------------------------------------------
# get_search_directories indirect tests (no patching — real filesystem)
# ---------------------------------------------------------------------------


def test_get_search_directories_includes_cwd(tmp_path):
    """
    get_search_directories is exercised indirectly: with a real AGENTS.md in
    the CWD-like directory, create_project_context_prompt picks it up without
    any patching.

    We cannot easily control CWD in all environments, so we simply verify that
    calling the handler without patching does not crash and returns a string.
    """
    handler = create_project_context_prompt()
    ctx = _make_ctx()

    # No patch — uses real get_search_directories
    result = handler(ctx, "probe-prompt", _identity_next)

    assert isinstance(result, str)
    assert "probe-prompt" in result
