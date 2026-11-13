"""The shell judge's one line, carried from the cascade to the prompt (ADR-0141).

A verdict is decided in ``agent/run/deferred_calls.py`` and drawn by
``handler.py::format_approval_message``, which is handed only the
``ToolCallPart``. The line travels keyed by the per-call-unique
``tool_call_id``, the same shape ``override_registry`` uses for the same
reason: the two ends of an approval sit in different layers of the run.

The four levels live here rather than in the judge because this module is the
lower of the two: ``agent/`` may import ``tool_call/`` and not the reverse.
"""

from __future__ import annotations

from zrb.util.truncate import truncate_display

#: The command looks like what its purpose says, with no blast radius the judge
#: can see. The only level that may be auto-approved.
JUDGE_SAFE = "safe"
#: Something the person answering should weigh: an irreversibility, a write
#: outside the workspace, a network reach, a consent gap.
JUDGE_CAUTION = "caution"
#: The command destroys or exfiltrates something, or asks for the sandbox.
JUDGE_DANGEROUS = "dangerous"
#: The judge did not finish, or answered in no shape we can read. Never safe.
JUDGE_UNKNOWN = "unknown"

# One reason, not a paragraph. Long enough for "deletes build/ with no undo",
# short enough that the command below it still reads as the thing to check.
MAX_JUDGE_REASON_CHARS = 200

# A level is one of four words; anything else is a model that ignored the
# schema, which is the same as no answer. Bare codepoints, no U+FE0F: a
# variation selector renders one column narrow in many terminals.
_GLYPHS = {
    JUDGE_SAFE: "⚖",
    JUDGE_CAUTION: "⚠",
    JUDGE_DANGEROUS: "🛑",
    JUDGE_UNKNOWN: "❔",
}

_pending: dict[str, tuple[str, str]] = {}


def record_judge_note(tool_call_id: str, level: str, reason: str) -> None:
    """Remember what the judge said about *tool_call_id*."""
    _pending[tool_call_id] = (level, reason)


def discard_judge_note(tool_call_id: str | None) -> None:
    """Drop the record once the call has its verdict, or will never be asked."""
    if tool_call_id is None:
        return
    _pending.pop(tool_call_id, None)


def read_judge_note(tool_call_id: str | None) -> tuple[str, str] | None:
    """The ``(level, reason)`` recorded for *tool_call_id*, if any.

    Read, not consumed: a prompt can be drawn more than once for one call (a
    response handler that asks again), and the line belongs on each of them.
    """
    if tool_call_id is None:
        return None
    return _pending.get(tool_call_id)


def format_judge_line(tool_call_id: str | None) -> str:
    """The judge's verdict as one indented line of the prompt, or `""`.

    Flattened to a single line with its control characters dropped, for the
    same reason `format_purpose_line` is: a reason is model output, and model
    output must not be able to redraw the prompt someone is about to answer.
    """
    note = read_judge_note(tool_call_id)
    if note is None:
        return ""
    level, reason = note
    glyph = _GLYPHS.get(level, _GLYPHS[JUDGE_UNKNOWN])
    printable = "".join(char if char.isprintable() else " " for char in reason)
    shown = " ".join(printable.split())
    if not shown:
        return f"       {glyph} judged: {level}\n"
    shown = truncate_display(shown, MAX_JUDGE_REASON_CHARS)
    return f"       {glyph} judged {level}: {shown}\n"
