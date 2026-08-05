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

import pytest

from zrb.llm.tool.post_write_check import (
    format_post_write_diagnostics,
    reset_diagnostic_counts,
)


@pytest.fixture(autouse=True)
def _clean_counts():
    reset_diagnostic_counts()
    yield
    reset_diagnostic_counts()


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


def _diagnose(path) -> str:
    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": False, "diagnostics": []}),
    ):
        return _run(format_post_write_diagnostics(str(path)))


def _diagnose_repeatedly(path, times: int) -> list[str]:
    """Run N diagnostics inside ONE event loop.

    The per-file counter is a ContextVar, and each ``asyncio.run`` starts from a
    fresh copy of the context — so separate runs would each look like a first
    failure. Production awaits these within one agent run.
    """

    async def _all():
        return [await format_post_write_diagnostics(str(path)) for _ in range(times)]

    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": False, "diagnostics": []}),
    ):
        return _run(_all())


def test_diagnostic_carries_actionable_system_suggestion(tmp_path):
    """A diagnostic is an error the model must recover from, so per AGENTS.md it
    carries a `[SYSTEM SUGGESTION]` naming the next action. The first failure
    says re-read then edit; escalation is a separate rung."""
    path = tmp_path / "broken.py"
    path.write_text("def f(:\n    pass\n")

    result = _diagnose(path)

    assert "[SYSTEM SUGGESTION]" in result
    # Names the next action rather than restating the problem.
    assert "`Read`" in result
    # Contradicts the caller's "Successfully updated ..." framing.
    assert "treat this as a failed edit" in result


def test_a_repeat_failure_escalates_to_a_whole_file_rewrite(tmp_path):
    """The escalation must be stated, not left to the model's own bookkeeping.

    Phrasing it as "if this file already reported errors on a previous write"
    asks a small model to track its own history. It does not: one trial spent 45
    alternating Read/Edit calls on a single file, never escalating.
    """
    path = tmp_path / "broken.py"
    path.write_text("def f(:\n    pass\n")

    first, second = _diagnose_repeatedly(path, 2)

    assert "failure 2 on broken.py" in second
    assert "Stop editing it" in second
    assert "single `Write`" in second
    assert "Stop editing it" not in first


def test_the_escalation_does_not_argue_against_its_own_escape_hatch(tmp_path):
    """Regression: a caveat about `Write` reverting unseen edits was read as a
    reason to avoid `Write`, and the loop it was meant to break got worse. The
    read is the rewrite's first step, not a warning attached to it."""
    path = tmp_path / "broken.py"
    path.write_text("def f(:\n    pass\n")

    _first, second = _diagnose_repeatedly(path, 2)

    assert "reverts the edits" not in second
    # Read is sequenced before the write, not offered as an alternative to it.
    assert second.index("`Read`") < second.index("single `Write`")


def test_counts_are_tracked_per_file(tmp_path):
    """A second file's first failure is still a first failure."""
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    for p in (a, b):
        p.write_text("def f(:\n    pass\n")

    async def _mixed():
        from zrb.llm.tool.post_write_check import format_post_write_diagnostics as f

        await f(str(a))
        await f(str(a))
        return await f(str(b))

    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": False, "diagnostics": []}),
    ):
        b_first = _run(_mixed())

    assert "Stop editing it" not in b_first


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
