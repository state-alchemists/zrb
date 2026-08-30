"""Interactive user-question tool.

`ask_user_question` lets the model pose structured multiple-choice questions
to the user mid-turn. Renders through the active `UIProtocol.ask_user`. In
non-interactive mode (`zrb llm chat --interactive false`) the tool
short-circuits with a `[SYSTEM SUGGESTION]` error so the model never blocks
on stdin in a non-interactive run. That suggestion offers two terminal exits
— decide-and-continue or stop-and-report — and forbids a retry, so an
unanswerable question cannot become a re-ask loop.

The interactive flag is propagated via the `interactive_mode` ContextVar, set
per turn by `live_context._wire_ambient_state` from `ctx.input.interactive`.
Sub-agents inherit the parent's value through ContextVar's asyncio-task
semantics.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Annotated, Any, cast

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.agent_state import get_current_ui
from zrb.llm.hook.manager import hook_manager
from zrb.llm.hook.types import HookEvent
from zrb.llm.tool.wrapper import tool_safe_async
from zrb.llm.tool_call.always_approve import register_always_auto_approve
from zrb.llm.tool_call.choice_spec_format import format_choice_spec

if TYPE_CHECKING:
    from zrb.llm.tool_call.ui_protocol import ChoiceSpec

interactive_mode: ContextVar[bool] = ContextVar("zrb_interactive_mode", default=True)


def get_interactive_mode() -> bool:
    """Return whether the current chat session is interactive."""
    return interactive_mode.get()


def set_interactive_mode(value: bool) -> None:
    """Set the interactive flag for the current chat session."""
    interactive_mode.set(value)


@tool_safe_async
async def ask_user_question(
    questions: Annotated[
        list[dict[str, Any]],
        Field(
            description=(
                "One or more questions to ask. Each entry must have: "
                "`question` (str) the question text; `options` (list[dict]) "
                "each with `label` (str) and optional `description` (str); "
                "`multi_select` (bool, optional, default False) True to allow "
                "multiple selections; `header` (str, optional) short label "
                "(≤12 chars) shown as a chip."
            )
        ),
    ],
) -> str:
    """
    Ask the user one or more structured multiple-choice questions and return the answers.

    The user may also type free-form text instead of selecting a labeled option;
    that text is returned verbatim.

    Returns: a structured string listing each question's answer.

    Non-interactive mode: returns a `[SYSTEM SUGGESTION]` error directing the
    model to either decide and continue or stop and report the open choice.
    Never blocks on stdin in that mode.
    """
    if not get_interactive_mode():
        return (
            "[SYSTEM SUGGESTION]: AskUserQuestion is unavailable in non-interactive "
            "mode. Do not call it again this turn. Pick one: (a) make your best "
            "judgement from the conversation so far, name the assumption, and "
            "continue; or (b) if a wrong pick would waste the work, stop and "
            "report the choice you could not make."
        )
    if not questions:
        return (
            "Error: no questions provided. "
            "[SYSTEM SUGGESTION]: provide at least one question with `question` "
            "and `options` keys, or do not call this tool."
        )

    ui = get_current_ui()
    if ui is None:
        return (
            "[SYSTEM SUGGESTION]: No UI is available to render the question. "
            "Do not call it again this turn. Either make your best judgement, "
            "name the assumption, and continue, or stop and report the choice "
            "you could not make."
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

    # Notify that the agent is now blocking on a user question so "needs your
    # input" notifications/sounds (e.g. peon-ping) ring. AskUserQuestion is
    # auto-approved (ADR-0062), so it never reaches the PermissionRequest path
    # in the approval cascade — this is its only attention signal.
    await _notify_question_pending(questions)

    total = len(questions)
    answers: list[str] = []
    for idx, q in enumerate(questions, start=1):
        spec = build_choice_spec(idx, total, q)
        try:
            if hasattr(ui, "ask_user_choice"):
                raw = await ui.ask_user_choice(cast("ChoiceSpec", spec))
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


async def _notify_question_pending(questions: list[dict[str, Any]]) -> None:
    """Fire a Notification so input-required hooks ring while a question is open.

    Uses ``notification_type='elicitation_dialog'`` — the type Claude-compatible
    consumers (peon-ping) map to "question pending" / input required; a generic
    notification with no type is suppressed as unknown. Best-effort: a hook
    failure must never break the prompt.
    """
    try:
        await hook_manager.execute_hooks(
            HookEvent.NOTIFICATION,
            {"questions": questions},
            message="Waiting for your answer to a question",
            notification_type="elicitation_dialog",
        )
    except Exception as e:
        CFG.LOGGER.debug(f"Notification hook for ask failed: {e}")


def build_choice_spec(idx: int, total: int, q: dict[str, Any]) -> dict[str, Any]:
    header = q.get("header") or q.get("question", "").strip().rstrip("?")[:40]
    return {
        "question": q["question"],
        "options": q["options"],
        "multi_select": bool(q.get("multi_select")),
        "header": header,
        "index": idx,
        "total": total,
    }


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
        resolved = [lbl for lbl in labels if lbl is not None]
        if resolved and len(resolved) == len(labels):
            return ", ".join(resolved)
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
