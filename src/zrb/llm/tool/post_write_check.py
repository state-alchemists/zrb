"""Post-write/post-edit diagnostics for ``Write`` and ``Edit`` results.

Merges LSP errors with a static check (Python: ``ast`` + ``pyflakes``),
deduplicated by ``(line, message)``. The static check always runs because
servers differ in severity (pylsp may report undefined names as warnings).
"""

from __future__ import annotations

import ast
import os

from zrb.llm.lsp.manager import lsp_manager

_MAX_ERRORS_SHOWN = 5


async def format_post_write_diagnostics(abs_path: str) -> str:
    """A ``[DIAGNOSTIC]`` block when the edit introduced errors, else ``""``.

    The ``[SYSTEM SUGGESTION]`` tells the model to re-read before editing
    again: without it, models answered the diagnostic with blind edits.
    """
    if not os.path.isfile(abs_path):
        return ""

    lsp_errors = await _query_lsp_errors(abs_path)
    static_errors = _static_check_errors(abs_path)
    seen: set[tuple[int, str]] = set()
    errors: list[tuple[int, str]] = []
    for line, msg in (lsp_errors or []) + static_errors:
        key = (line, msg.strip())
        if key in seen:
            continue
        seen.add(key)
        errors.append((line, msg))
    if not errors:
        return ""

    preview = "\n".join(
        f"  L{line}: {msg.strip()}" for line, msg in errors[:_MAX_ERRORS_SHOWN]
    )
    overflow = (
        f"\n  ... and {len(errors) - _MAX_ERRORS_SHOWN} more"
        if len(errors) > _MAX_ERRORS_SHOWN
        else ""
    )
    return (
        f"FAILED: the bytes reached disk, but {abs_path} is now broken — "
        "treat this as a failed edit, not a completed one.\n"
        f"[DIAGNOSTIC]: {len(errors)} error(s):\n"
        f"{preview}{overflow}\n"
        "[SYSTEM SUGGESTION]: Do not issue another edit to this file from memory. "
        "`Read` the file (or the lines above) to see its current state first, then "
        "make one targeted fix. If the errors "
        "name something outside this file (a missing import, an undefined symbol "
        "defined elsewhere), fix that file rather than re-editing this one."
    )


def compose_write_result(outcome: str, diagnostics: str) -> str:
    """Join a write tool's *outcome* line to its post-write *diagnostics*.

    Diagnostics lead: a result opening with "Successfully updated" reads as
    success to the model however the body contradicts it.
    """
    if not diagnostics:
        return outcome
    return f"{diagnostics}\n\nWhat landed: {outcome}"


async def _query_lsp_errors(abs_path: str) -> list[tuple[int, str]]:
    """LSP-reported errors for the file, or ``[]`` when LSP has none or fails."""
    try:
        result = await lsp_manager.get_diagnostics(abs_path, severity="error")
    except Exception:
        return []
    if not isinstance(result, dict) or not result.get("found"):
        return []
    diagnostics = result.get("diagnostics") or []
    if not isinstance(diagnostics, list):
        return []
    return [(d.get("line", 1), d.get("message", "")) for d in diagnostics]


def _static_check_errors(abs_path: str) -> list[tuple[int, str]]:
    if abs_path.endswith(".py"):
        return _python_static_errors(abs_path)
    return []


def _python_static_errors(abs_path: str) -> list[tuple[int, str]]:
    """Syntax errors and undefined names only; unused-name warnings are mid-edit noise."""
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return []

    try:
        tree = ast.parse(content, filename=abs_path)
    except SyntaxError as e:
        line = e.lineno or 1
        return [(line, f"SyntaxError: {e.msg}")]

    try:
        # lazy: heavy third-party — pyflakes is optional
        from pyflakes import checker as _pyflakes_checker
        from pyflakes.messages import UndefinedExport, UndefinedLocal, UndefinedName
    except Exception:
        return []

    blocking = (UndefinedName, UndefinedExport, UndefinedLocal)
    chk = _pyflakes_checker.Checker(tree, filename=abs_path)
    out: list[tuple[int, str]] = []
    for msg in chk.messages:
        if not isinstance(msg, blocking):
            continue
        try:
            human = msg.message % msg.message_args
        except Exception:
            human = str(msg)
        out.append((msg.lineno, human))
    return out
