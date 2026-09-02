from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.context.any_context import zrb_print
from zrb.llm.tool_call.args import parse_tool_args
from zrb.llm.tool_call.handler import MAX_DENIAL_REASON_CHARS
from zrb.util.truncate import truncate_chars

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolApproved, ToolCallPart, ToolDenied
    from zrb.llm.ui.any_ui import AnyUI


async def default_response_handler(
    ui: AnyUI,
    call: ToolCallPart,
    user_response: str,
    next_handler: Callable[[AnyUI, ToolCallPart, str], Awaitable[Any]],
) -> ToolApproved | ToolDenied | None:
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ToolApproved, ToolDenied

    # lazy: tests patch `zrb.llm.tool_call.edit_util.edit_content_via_editor`
    # at the source path and rely on the patch taking effect inside this
    # function. Hoisting would bind the name at module-load.
    from zrb.llm.tool_call.edit_util import edit_content_via_editor

    # end="": this also writes to the shared audit log (can't drop it), but
    # its default trailing "\n" stacked with `resolve_current`'s own echo of
    # the same answer, adding a full blank line after every confirmation —
    # worst for the common empty-answer case (hit Enter to approve), where
    # this contributed a bare "\n" with no text to justify it.
    zrb_print(user_response, end="", plain=True)

    # Two-space indent on every line here, matching `StreamEventHandler`'s own
    # `indentation` (the only value zrb ever constructs it with) — these print
    # outside that handler entirely, so without it they land at column 0 while
    # everything else in the trace (thinking, tool-call, usage) is indented.
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
                return None  # Signal loop retry

            if new_args == args:
                ui.append_to_output("\n  ℹ️ No changes made.")
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
