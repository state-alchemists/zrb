"""Shared post-write/post-edit diagnostic helper.

Called by ``write_file`` and ``replace_in_file`` so the tool result surfaces
errors the edit may have introduced (missing imports, undefined names, syntax
errors). Stays silent when no checker is available for the file's language so
non-code edits (``.md``, ``.txt``, etc.) don't get spurious diagnostics.

Strategy is tiered:

1. **LSP** (preferred) — ask the running LSP server via
   :func:`lsp_manager.get_diagnostics`. This currently returns nothing for
   newly-written files because zrb's LSP layer doesn't ``didOpen`` files and
   most servers don't support pull-diagnostics; the call is left in place so
   the path lights up automatically when that plumbing is fixed.
2. **Language-specific static check** (fallback) — for Python, parse with
   :mod:`ast` (catches ``SyntaxError``) and run :mod:`pyflakes` (catches
   ``UndefinedName`` etc.). Other languages currently fall through silently.
"""

from __future__ import annotations

import ast
import os

from zrb.llm.lsp.manager import lsp_manager

_MAX_ERRORS_SHOWN = 5


async def format_post_write_diagnostics(abs_path: str) -> str:
    """Return a ``[DIAGNOSTIC]`` suffix when the edit introduced errors.

    Returns ``""`` when the file no longer exists, the language is not
    supported by any available checker, or the file is error-free. The
    caller appends the returned string directly to its success message — an
    empty return means the tool result is unchanged.
    """
    if not os.path.isfile(abs_path):
        return ""

    errors = await _query_lsp_errors(abs_path)
    if errors is None:
        errors = _static_check_errors(abs_path)
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
        f"\n\n[DIAGNOSTIC]: {len(errors)} error(s) detected in {abs_path}:\n"
        f"{preview}{overflow}\n"
        f"Fix these before continuing — the edit may have introduced a regression."
    )


async def _query_lsp_errors(abs_path: str) -> list[tuple[int, str]] | None:
    """Return LSP-reported errors, or ``None`` when LSP didn't yield anything.

    ``None`` (not ``[]``) signals the caller to try the static-check fallback.
    An empty list means LSP authoritatively reported a clean file.
    """
    try:
        result = await lsp_manager.get_diagnostics(abs_path, severity="error")
    except Exception:
        return None
    if not result.get("found"):
        return None
    return [
        (d.get("line", 1), d.get("message", ""))
        for d in result.get("diagnostics") or []
    ]


def _static_check_errors(abs_path: str) -> list[tuple[int, str]]:
    """Language-dispatch for the static-check fallback."""
    if abs_path.endswith(".py"):
        return _python_static_errors(abs_path)
    return []


def _python_static_errors(abs_path: str) -> list[tuple[int, str]]:
    """Run ``ast.parse`` then ``pyflakes`` against a Python file.

    Reports only high-signal "you broke it" issues: syntax errors and
    undefined names. Ignores unused-import / unused-variable warnings —
    those are common in mid-edit states and would just nag the model.
    """
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
