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

# One circle per level, in front of the word. The word is what a reader decides
# on and is still there; the circle is what keeps a `dangerous` line from being
# skimmed as one more line of the prompt, which is the fatigue ADR-0141 opened
# on. Every line of that prompt leads with a glyph already.
#
# These four are wide by default — `wcwidth` answers two for each — so, unlike a
# symbol turned emoji by a variation selector, one cannot overwrite the letter
# after it. The white circle is the only one terminals present differently:
# counted at two columns, drawn at one where it stays text, which leaves a gap
# rather than a lost letter. It is also the level where the line reads oddly
# anyway, and the word `unknown` says what it means.
JUDGE_GLYPHS = {
    JUDGE_SAFE: "🟢",
    JUDGE_CAUTION: "🟡",
    JUDGE_DANGEROUS: "🔴",
    JUDGE_UNKNOWN: "⚪",
}

_pending: dict[str, tuple[str, str, str]] = {}


def record_judge_note(
    tool_call_id: str, level: str, reason: str, facts: str = ""
) -> None:
    """Remember what the judge said about *tool_call_id*, and what it saw."""
    _pending[tool_call_id] = (level, reason, facts)


def discard_judge_note(tool_call_id: str | None) -> None:
    """Drop the record once the call has its verdict, or will never be asked."""
    if tool_call_id is None:
        return
    _pending.pop(tool_call_id, None)


def read_judge_note(tool_call_id: str | None) -> tuple[str, str, str] | None:
    """The ``(level, reason, facts)`` recorded for *tool_call_id*, if any.

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
    The circle leads and the level word follows it, so the line survives being
    read at a glance and being read exactly.

    The facts in parentheses come from `git status` and the call's arguments,
    not from the model: they are the half of the line a reader can check.
    """
    note = read_judge_note(tool_call_id)
    if note is None:
        return ""
    level, reason, facts = note
    glyph = JUDGE_GLYPHS.get(level, JUDGE_GLYPHS[JUDGE_UNKNOWN])
    shown_facts = (
        " (" + " ".join(facts.split()) + ")" if facts and facts.strip() else ""
    )
    printable = "".join(char if char.isprintable() else " " for char in reason)
    shown = " ".join(printable.split())
    if not shown:
        return f"       {glyph} judged: {level}{shown_facts}\n"
    shown = truncate_display(shown, MAX_JUDGE_REASON_CHARS)
    return f"       {glyph} judged {level}{shown_facts}: {shown}\n"
