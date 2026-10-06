from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.context.any_context import zrb_print
from zrb.llm.tool_call.args import parse_tool_args
from zrb.llm.tool_call.handler import MAX_DENIAL_REASON_CHARS
from zrb.util.truncate import truncate_chars

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolApproved, ToolCallPart, ToolDenied
    from zrb.llm.ui.any_agent_output import AnyAgentOutput


async def default_response_handler(
    ui: AnyAgentOutput,
    call: ToolCallPart,
    user_response: str,
    next_handler: Callable[[AnyAgentOutput, ToolCallPart, str], Awaitable[Any]],
) -> ToolApproved | ToolDenied | None:
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ToolApproved, ToolDenied

    # lazy: tests patch zrb.llm.tool_call.edit_util.edit_content_via_editor; hoisting bypasses the mock
    from zrb.llm.tool_call.edit_util import edit_content_via_editor

    # end="": `resolve_current` already echoes the answer's newline.
    zrb_print(user_response, end="", plain=True)

    # Two-space indent matches `StreamEventHandler`'s indentation.
    if user_response.lower().strip() in ("y", "yes", "ok", "okay", ""):
        ui.append_to_output("\n  ✅ Execution approved.")
        return ToolApproved()
    elif user_response.lower().strip() in ("n", "no"):
        ui.append_to_output("\n  🛑 Execution denied.")
        return ToolDenied("User denied execution")
    elif user_response.lower().strip() in ("e", "edit"):
        try:
            args = parse_tool_args(call) or {}

            new_args = await edit_content_via_editor(ui, args)

            if new_args is None:
                ui.append_to_output("\n  ❌ Invalid format. ", end="")
                return None  # retry

            if new_args == args:
                ui.append_to_output("\n  🔹 No changes made.")
                return None

            ui.append_to_output("\n  ✅ Execution approved (with modification).")
            return ToolApproved(override_args=new_args)

        except Exception as e:
            ui.append_to_output(f"\n  ❌ Error editing: {e}. ", end="")
            return None
    else:
        reason = truncate_chars(user_response, MAX_DENIAL_REASON_CHARS)
        ui.append_to_output("\n  🛑 Execution denied.")
        ui.append_to_output(f"\n  🛑 Reason: {reason}")
        return ToolDenied(f"User denied execution with message: {reason}")
