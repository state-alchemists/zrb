"""Interactive user-question tool.

`ask_user_question` lets the model pose structured multiple-choice questions
to the user mid-turn. Renders through the active `UIProtocol.ask_user`. In
non-interactive mode (`zrb llm chat --interactive false`) the tool
short-circuits with a `[SYSTEM SUGGESTION]` error so the model never blocks
on stdin in a non-interactive run.

The interactive flag is propagated via the `interactive_mode` ContextVar,
set by the `system_context` prompt middleware from `ctx.input.interactive`
once per prompt build. Sub-agents inherit the parent's value through
ContextVar's asyncio-task semantics.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from zrb.llm.tool.wrapper import tool_safe_async
from zrb.llm.tool_call.always_approve import register_always_auto_approve

interactive_mode: ContextVar[bool] = ContextVar("zrb_interactive_mode", default=True)


def get_interactive_mode() -> bool:
    """Return whether the current chat session is interactive."""
    return interactive_mode.get()


def set_interactive_mode(value: bool) -> None:
    """Set the interactive flag for the current chat session."""
    interactive_mode.set(value)


@tool_safe_async
async def ask_user_question(questions: list[dict[str, Any]]) -> str:
    """
    Ask the user one or more structured multiple-choice questions and return the answers.

    Use ONLY when the choice is non-obvious AND the wrong choice would waste
    significant work. Do not ask for permission to do obvious things — decide
    and proceed.

    Each entry in `questions` must have:
      - `question` (str): the question text.
      - `options` (list[dict]): each with `label` (str) and optional `description` (str).
      - `multi_select` (bool, optional): True to allow multiple selections. Default False.
      - `header` (str, optional): short label (≤12 chars) shown as a chip.

    The user may also type free-form text instead of selecting a labeled option;
    that text is returned verbatim.

    Returns: a structured string listing each question's answer.

    Non-interactive mode: returns a `[SYSTEM SUGGESTION]` error directing the
    model to decide and continue. Never blocks on stdin in that mode.
    """
    if not get_interactive_mode():
        return (
            "[SYSTEM SUGGESTION]: AskUserQuestion is unavailable in non-interactive "
            "mode. Make your best judgement based on the conversation so far and "
            "continue."
        )
    if not questions:
        return "Error: no questions provided."

    # lazy: circular — tool → agent.run.runtime_state → ... → tool
    from zrb.llm.agent.run.runtime_state import get_current_ui

    ui = get_current_ui()
    if ui is None:
        return (
            "[SYSTEM SUGGESTION]: No UI is available to render the question. "
            "Make your best judgement and continue."
        )

    required = ("question", "options")
    for idx, q in enumerate(questions):
        missing = [k for k in required if k not in q]
        if missing:
            return (
                f"Error: questions[{idx}] missing required keys: {missing}. "
                "[SYSTEM SUGGESTION]: each question needs `question` and `options`."
            )
        if not q.get("options"):
            return (
                f"Error: questions[{idx}].options is empty. "
                "[SYSTEM SUGGESTION]: provide at least two options or do not ask."
            )

    total = len(questions)
    answers: list[str] = []
    for idx, q in enumerate(questions, start=1):
        spec = _build_choice_spec(idx, total, q)
        try:
            if hasattr(ui, "ask_user_choice"):
                raw = await ui.ask_user_choice(spec)
            else:
                # Custom UI predating ask_user_choice — fall back to text.
                raw = await ui.ask_user(format_choice_spec(spec))
        except (KeyboardInterrupt, EOFError):
            return (
                "[SYSTEM SUGGESTION]: User cancelled the question prompt. "
                "Stop and report what you've done so far."
            )
        resolved = _resolve_answer(q, raw)
        header = q.get("header") or q.get("question", "").strip().rstrip("?")[:40]
        answers.append(f"Q{idx} ({header}): {resolved}")
    return "\n".join(answers)


def _build_choice_spec(idx: int, total: int, q: dict[str, Any]) -> dict[str, Any]:
    header = q.get("header") or q.get("question", "").strip().rstrip("?")[:40]
    return {
        "question": q["question"],
        "options": q["options"],
        "multi_select": bool(q.get("multi_select")),
        "header": header,
        "index": idx,
        "total": total,
    }


def format_choice_spec(spec: dict[str, Any]) -> str:
    """Render a `ChoiceSpec` as numbered text (fallback for non-widget UIs)."""
    multi = bool(spec.get("multi_select"))
    idx = spec.get("index", 1)
    total = spec.get("total", 1)
    counter = f"{idx}/{total}" if total > 1 else f"{idx}"
    lines: list[str] = [f"\n[Q{counter}] {spec['question']}"]
    for i, opt in enumerate(spec.get("options", []), start=1):
        label = opt.get("label", f"Option {i}")
        desc = opt.get("description", "")
        suffix = f" — {desc}" if desc else ""
        lines.append(f"  {i}. {label}{suffix}")
    hint = (
        "Reply with comma-separated numbers (e.g. 1,3) or free-form text: "
        if multi
        else "Reply with a number or free-form text: "
    )
    lines.append(hint)
    return "\n".join(lines)


def _resolve_answer(q: dict[str, Any], raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return "(no answer)"
    options = q["options"]
    multi = bool(q.get("multi_select"))

    def pick(token: str) -> str | None:
        token = token.strip()
        if not token.isdigit():
            return None
        i = int(token) - 1
        if 0 <= i < len(options):
            return options[i].get("label", token)
        return None

    if multi:
        parts = [p for p in raw.split(",") if p.strip()]
        labels = [pick(p) for p in parts]
        if labels and all(lbl is not None for lbl in labels):
            return ", ".join(labels)
        return raw
    picked = pick(raw)
    return picked if picked is not None else raw


ask_user_question.__name__ = "AskUserQuestion"

# AskUserQuestion *is* the user interaction — gating it behind a separate
# tool-approval prompt is meaningless and renders before the question itself.
# Auto-approve intrinsically, in every path (main agent, sub-agents, web), so
# the question surfaces directly. The non-interactive guard above already
# prevents the tool from blocking on stdin when there is no user to answer.
register_always_auto_approve("AskUserQuestion")
