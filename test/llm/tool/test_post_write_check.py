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


def test_the_suggestion_never_prescribes_a_whole_file_rewrite(tmp_path):
    """The escalation that used to live here prescribed its own trigger.

    "`Read` the file in full, then replace it in a single `Write`" asks for a
    whole-file rewrite; a small model's rewrite regenerates the diagnostic, which
    re-issues the instruction. An A/B on gpt-4o-mini isolated it — the
    ``refactor`` challenge took 10 tool calls without the ladder and 51 with it,
    and the arm's total calls rose 215 -> 366 while the pass rate fell 11/18 ->
    8/18. What survives asks for *one targeted fix*, which an `Edit` satisfies
    without restarting the cycle.
    """
    path = tmp_path / "broken.py"
    path.write_text("def f(:\n    pass\n")

    messages = _diagnose_repeatedly(path, 3)

    for m in messages:
        assert "single `Write`" not in m
        assert "Stop editing it" not in m
        assert "replace it in a single" not in m
    assert "one targeted fix" in messages[0]


def test_the_suggestion_is_bounded_then_goes_silent(tmp_path):
    """Past two tries the only lever left is to stop talking.

    A third rung was tried, at length, telling the model to stop and report. One
    trial received it 22 times and kept going. Advice already being ignored is
    not made effective by repetition, and every appended instruction is something
    to react to instead of the errors. The errors keep being reported in full.
    """
    path = tmp_path / "broken.py"
    path.write_text("def f(:\n    pass\n")

    messages = _diagnose_repeatedly(path, 5)

    assert all("[DIAGNOSTIC]" in m for m in messages), "errors stay reported"
    assert all("[SYSTEM SUGGESTION]" in m for m in messages[:2])
    assert all("[SYSTEM SUGGESTION]" not in m for m in messages[2:])
    # Nothing dangles where the suggestion used to be.
    assert messages[-1].rstrip().endswith("not a completed one.")


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
        await f(str(a))  # a is now past the bound and silent
        return await f(str(b))

    with patch(
        "zrb.llm.tool.post_write_check.lsp_manager.get_diagnostics",
        new=AsyncMock(return_value={"found": False, "diagnostics": []}),
    ):
        b_first = _run(_mixed())

    assert "[SYSTEM SUGGESTION]" in b_first


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


@pytest.mark.asyncio
async def test_a_compliant_read_write_cycle_stops_being_instructed(tmp_path):
    """The end-to-end shape of the loop the A/B measured, through the real tools.

    A model that obeys the suggestion exactly — `Read`, then `Write` — and still
    cannot fix the file used to receive an instruction every single cycle: first
    the whole-file-rewrite prescription (which regenerates the diagnostic that
    re-issues it), then a "stop and report" rung that one trial ignored 22 times.
    Now the instruction stops after two, and only the errors keep coming.
    """
    from zrb.llm.tool.file_read import read_file
    from zrb.llm.tool.file_write import write_file

    p = tmp_path / "main.py"
    broken = "def run(:\n    return 1\n"
    p.write_text(broken)

    messages = []
    for _ in range(6):
        read_file(str(p))
        messages.append(await write_file(str(p), broken))

    assert all("[DIAGNOSTIC]" in m for m in messages), "the file must stay broken"
    assert sum("[SYSTEM SUGGESTION]" in m for m in messages) == 2
    # Nothing in any cycle asks for the whole-file rewrite that fed the loop.
    assert all("single `Write`" not in m for m in messages)


@pytest.mark.asyncio
async def test_a_fixed_file_reports_nothing_further(tmp_path):
    """The ordinary recovery: one diagnostic, one suggestion, then silence.

    This is the path the bound must not disturb — a model that reads, fixes, and
    succeeds sees the guidance exactly once and gets a clean result afterwards.
    """
    from zrb.llm.tool.file_read import read_file
    from zrb.llm.tool.file_write import write_file

    p = tmp_path / "ok.py"
    p.write_text("def run(:\n    return 1\n")

    read_file(str(p))
    first = await write_file(str(p), "def run(:\n    return 1\n")
    read_file(str(p))
    second = await write_file(str(p), "def run():\n    return 1\n")

    assert "[DIAGNOSTIC]" in first
    assert "[SYSTEM SUGGESTION]" in first
    assert "one targeted fix" in first
    # The fix landed, so nothing is appended at all.
    assert "[DIAGNOSTIC]" not in second
    assert "[SYSTEM SUGGESTION]" not in second
    assert second.startswith("Successfully wrote")
