from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.context.any_context import zrb_print
from zrb.llm.tool_call.ui_protocol import UIProtocol

if TYPE_CHECKING:
    from pydantic_ai import ToolApproved, ToolCallPart, ToolDenied


async def default_response_handler(
    ui: UIProtocol,
    call: ToolCallPart,
    user_response: str,
    next_handler: Callable[[UIProtocol, ToolCallPart, str], Awaitable[Any]],
) -> ToolApproved | ToolDenied | None:
    from pydantic_ai import ToolApproved, ToolDenied

    from zrb.llm.tool_call.edit_util import edit_content_via_editor

    zrb_print(user_response, plain=True)

    if user_response.lower().strip() in ("y", "yes", "ok", "okay", ""):
        ui.append_to_output("\n✅ Execution approved.")
        return ToolApproved()
    elif user_response.lower().strip() in ("n", "no"):
        ui.append_to_output("\n🛑 Execution denied.")
        return ToolDenied("User denied execution")
    elif user_response.lower().strip() in ("e", "edit"):
        # Edit logic
        try:
            args = call.args
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    pass
            if not isinstance(args, dict):
                args = {}

            # Use shared editor utility
            new_args = await edit_content_via_editor(ui, args)

            if new_args is None:
                ui.append_to_output("\n❌ Invalid format. ", end="")
                return None  # Signal loop retry

            if new_args == args:
                ui.append_to_output("\nℹ️ No changes made.")
                return None

            ui.append_to_output("\n✅ Execution approved (with modification).")
            return ToolApproved(override_args=new_args)

        except Exception as e:
            ui.append_to_output(f"\n❌ Error editing: {e}. ", end="")
            return None
    else:
        ui.append_to_output("\n🛑 Execution denied.")
        ui.append_to_output(f"\n🛑 Reason: {user_response}")
        return ToolDenied(f"User denied execution with message: {user_response}")
