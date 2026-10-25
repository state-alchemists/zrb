"""Tests for the post-write diagnostic helper.

The key behavior to lock in: inside a project, LSP and the static checker are
*both* consulted and their results merged, so an undefined name pyflakes
catches still surfaces even when LSP filtered everything out by severity.
Earlier versions returned early on LSP `found=True` with empty filtered
diagnostics, silently dropping real errors.

Outside any project the LSP is not consulted at all: it has no import graph to
resolve against, so its module-resolution errors describe where the file sits
rather than what was written.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from zrb.llm.tool.post_write_check import (
    compose_write_result,
    format_post_write_diagnostics,
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def project_dir(tmp_path):
    """A bare-enough directory that still counts as a project, so the LSP is consulted."""
    (tmp_path / "pyproject.toml").write_text("")
    return tmp_path


def test_no_suffix_for_clean_python_file(tmp_path):
    path = tmp_path / "clean.py"
    path.write_text("x = 1\n")
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": False, "diagnostics": []}),
    ):
        result = _run(format_post_write_diagnostics(str(path)))
    assert result == ""


def test_no_suffix_for_missing_file(tmp_path):
    result = _run(format_post_write_diagnostics(str(tmp_path / "ghost.py")))
    assert result == ""


def test_no_suffix_for_non_python_file(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("not code\n")
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": False, "diagnostics": []}),
    ):
        result = _run(format_post_write_diagnostics(str(path)))
    assert result == ""


def test_syntax_error_surfaces_via_static_check(tmp_path):
    path = tmp_path / "broken.py"
    path.write_text("def f(:\n    pass\n")
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": False, "diagnostics": []}),
    ):
        result = _run(format_post_write_diagnostics(str(path)))
    assert "[DIAGNOSTIC]" in result
    assert "SyntaxError" in result


def test_diagnostic_carries_actionable_system_suggestion(tmp_path):
    """A diagnostic is an error the model must recover from, so per AGENTS.md it
    carries a `[SYSTEM SUGGESTION]` naming the next action — re-read before the
    next edit, and fix the named target. Without this the result reads as a
    completed success and invites another blind edit."""
    path = tmp_path / "broken.py"
    path.write_text("def f(:\n    pass\n")
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": False, "diagnostics": []}),
    ):
        result = _run(format_post_write_diagnostics(str(path)))

    assert "[SYSTEM SUGGESTION]" in result
    # Names the next action rather than restating the problem.
    assert "`Read`" in result
    # Does not prescribe a whole-file `Write`, which a model reads as a license
    # to rewrite from memory — the exact move that once shipped a regression.
    assert "whole file" not in result
    assert "`Write`" not in result
    # The verdict lives in this block and nowhere else, and leads it — the
    # caller composes it ahead of its own outcome line rather than repeating it.
    assert "treat this as a failed edit" in result
    assert result.startswith("FAILED:")


def test_clean_file_emits_no_suggestion(tmp_path):
    """The guidance rides along with a diagnostic — never on a clean write."""
    path = tmp_path / "fine.py"
    path.write_text("def f():\n    return 1\n")
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": False, "diagnostics": []}),
    ):
        result = _run(format_post_write_diagnostics(str(path)))

    assert result == ""


def test_undefined_name_surfaces_when_lsp_empty_but_found(project_dir):
    """Regression: LSP `found=True` with empty filtered errors must NOT skip
    the static check. pyflakes catches the undefined name; the user sees it."""
    path = project_dir / "typo.py"
    path.write_text("def main():\n    prnit('hi')\n")
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": True, "diagnostics": []}),
    ):
        result = _run(format_post_write_diagnostics(str(path)))
    assert "[DIAGNOSTIC]" in result
    assert "prnit" in result


def test_lsp_and_static_results_dedupe(project_dir):
    path = project_dir / "typo.py"
    path.write_text("def main():\n    prnit('hi')\n")
    # LSP reports the same undefined-name pyflakes will report. Should appear once.
    lsp_payload = {
        "found": True,
        "diagnostics": [{"line": 2, "message": "undefined name 'prnit'"}],
    }
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value=lsp_payload),
    ):
        result = _run(format_post_write_diagnostics(str(path)))
    assert result.count("undefined name 'prnit'") == 1


def test_lsp_exception_falls_through_to_static_check(project_dir):
    path = project_dir / "typo.py"
    path.write_text("def main():\n    prnit('hi')\n")
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(side_effect=RuntimeError("LSP exploded")),
    ):
        result = _run(format_post_write_diagnostics(str(path)))
    assert "[DIAGNOSTIC]" in result
    assert "prnit" in result


def test_lsp_returning_non_dict_does_not_crash(project_dir):
    """Defensive: future refactor returning None/list/etc. must not raise."""
    path = project_dir / "clean.py"
    path.write_text("x = 1\n")
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value=None),
    ):
        result = _run(format_post_write_diagnostics(str(path)))
    assert result == ""


def test_a_resolution_error_outside_a_project_is_dropped(tmp_path):
    """A helper written to a bare directory is still judged by its language server.

    But the server has no import graph around ``/tmp``, so ``could not be
    resolved`` describes the *location*. Reporting that as a failed edit is the
    false verdict this path exists to avoid, so that diagnostic is dropped —
    while the query itself still runs, because the same server is the only thing
    that can see a parse error in a language with no static fallback here."""
    path = tmp_path / "journal_merge.py"
    path.write_text("from zrb.llm.tool import journal_write\n")
    get_diagnostics = AsyncMock(
        return_value={
            "found": True,
            "diagnostics": [
                {"line": 1, "message": 'Import "zrb.llm.tool" could not be resolved'}
            ],
        }
    )
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=get_diagnostics,
    ):
        result = _run(format_post_write_diagnostics(str(path)))

    assert result == ""
    get_diagnostics.assert_called_once()


def test_a_parse_error_outside_a_project_still_fails(tmp_path):
    """Regression for the blanket gate: a JavaScript file in a bare directory has
    no pyflakes behind it, so dropping the LSP would have let a syntax error
    through as a clean write."""
    path = tmp_path / "scratch.js"
    path.write_text("const x = ;\n")
    get_diagnostics = AsyncMock(
        return_value={
            "found": True,
            "diagnostics": [{"line": 1, "message": "Unexpected token"}],
        }
    )
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=get_diagnostics,
    ):
        result = _run(format_post_write_diagnostics(str(path)))

    assert result.startswith("FAILED:")
    assert "Unexpected token" in result


def test_outside_a_project_only_the_intrinsic_diagnostic_survives(tmp_path):
    """A resolution error and a parse error arrive together; the parse error is
    the one about the file, so it is the one that reaches the model."""
    path = tmp_path / "scratch.js"
    path.write_text("const x = ;\n")
    get_diagnostics = AsyncMock(
        return_value={
            "found": True,
            "diagnostics": [
                {"line": 1, "message": "Cannot find module 'fs'"},
                {"line": 2, "message": "Unexpected token"},
            ],
        }
    )
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=get_diagnostics,
    ):
        result = _run(format_post_write_diagnostics(str(path)))

    assert result.startswith("FAILED:")
    assert "Unexpected token" in result
    assert "Cannot find module" not in result


def test_a_coded_resolution_error_is_recognised_without_its_wording(tmp_path):
    """Servers word it differently and may translate it; the code is the stable half."""
    path = tmp_path / "scratch.ts"
    path.write_text("import x from 'nope'\n")
    get_diagnostics = AsyncMock(
        return_value={
            "found": True,
            "diagnostics": [{"line": 1, "message": "nope", "code": 2307}],
        }
    )
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=get_diagnostics,
    ):
        result = _run(format_post_write_diagnostics(str(path)))

    assert result == ""


def test_import_inside_a_project_surfaces_the_lsp_verdict(project_dir):
    """The same import inside a project is a real signal, and still reaches the model."""
    path = project_dir / "journal_merge.py"
    path.write_text("from zrb.llm.tool import journal_write\n")
    get_diagnostics = AsyncMock(
        return_value={
            "found": True,
            "diagnostics": [
                {"line": 1, "message": 'Import "zrb.llm.tool" could not be resolved'}
            ],
        }
    )
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=get_diagnostics,
    ):
        result = _run(format_post_write_diagnostics(str(path)))

    assert result.startswith("FAILED:")
    assert "could not be resolved" in result
    get_diagnostics.assert_called_once()


def test_undefined_name_outside_a_project_still_fails(tmp_path):
    """The LSP is asked everywhere now; an undefined name is still pyflakes' to catch."""
    path = tmp_path / "typo.py"
    path.write_text("def main():\n    prnit('hi')\n")
    get_diagnostics = AsyncMock(return_value={"found": False, "diagnostics": []})
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=get_diagnostics,
    ):
        result = _run(format_post_write_diagnostics(str(path)))

    assert result.startswith("FAILED:")
    assert "prnit" in result
    get_diagnostics.assert_called_once()


def test_syntax_error_outside_a_project_still_fails(tmp_path):
    """A file that cannot be parsed is broken wherever it sits."""
    path = tmp_path / "broken.py"
    path.write_text("def f(:\n    pass\n")
    get_diagnostics = AsyncMock(return_value={"found": False, "diagnostics": []})
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=get_diagnostics,
    ):
        result = _run(format_post_write_diagnostics(str(path)))

    assert result.startswith("FAILED:")
    assert "SyntaxError" in result
    get_diagnostics.assert_called_once()


def test_compose_write_result_passes_a_clean_outcome_through():
    """No diagnostics means the tool result is exactly its outcome line."""
    assert compose_write_result("Successfully wrote to a.py", "") == (
        "Successfully wrote to a.py"
    )


def test_compose_write_result_leads_with_the_failure():
    """A broken write must not open with "Successfully". The first words of a
    tool result frame everything after them, so a result that opens with
    success reads as a completed step however firmly the body contradicts it —
    the shape that produced 81 consecutive blind edits. The outcome line is
    kept (the replacement count and fuzzy note are real signal) but demoted."""
    result = compose_write_result(
        "Successfully updated a.py (1 replacement(s))",
        "FAILED: the bytes reached disk, but a.py is now broken — treat this "
        "as a failed edit, not a completed one.\n[DIAGNOSTIC]: 1 error(s):",
    )

    assert result.startswith("FAILED:")
    assert not result.startswith("Successfully")
    # Demoted, not dropped.
    assert "1 replacement(s)" in result
    assert result.index("[DIAGNOSTIC]") < result.index("Successfully updated")
