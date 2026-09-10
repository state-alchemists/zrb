"""Tests for the post-write diagnostic helper.

The key behavior to lock in: LSP and the static checker are *both* consulted
and their results merged, so an undefined name pyflakes catches still surfaces
even when LSP filtered everything out by severity. Earlier versions returned
early on LSP `found=True` with empty filtered diagnostics, silently dropping
real errors.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from zrb.llm.tool.post_write_check import format_post_write_diagnostics


def _run(coro):
    return asyncio.run(coro)


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
    # Contradicts the caller's "Successfully updated ..." framing.
    assert "treat this as a failed edit" in result


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


def test_undefined_name_surfaces_when_lsp_empty_but_found(tmp_path):
    """Regression: LSP `found=True` with empty filtered errors must NOT skip
    the static check. pyflakes catches the undefined name; the user sees it."""
    path = tmp_path / "typo.py"
    path.write_text("def main():\n    prnit('hi')\n")
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": True, "diagnostics": []}),
    ):
        result = _run(format_post_write_diagnostics(str(path)))
    assert "[DIAGNOSTIC]" in result
    assert "prnit" in result


def test_lsp_and_static_results_dedupe(tmp_path):
    path = tmp_path / "typo.py"
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


def test_lsp_exception_falls_through_to_static_check(tmp_path):
    path = tmp_path / "typo.py"
    path.write_text("def main():\n    prnit('hi')\n")
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(side_effect=RuntimeError("LSP exploded")),
    ):
        result = _run(format_post_write_diagnostics(str(path)))
    assert "[DIAGNOSTIC]" in result
    assert "prnit" in result


def test_lsp_returning_non_dict_does_not_crash(tmp_path):
    """Defensive: future refactor returning None/list/etc. must not raise."""
    path = tmp_path / "clean.py"
    path.write_text("x = 1\n")
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value=None),
    ):
        result = _run(format_post_write_diagnostics(str(path)))
    assert result == ""
