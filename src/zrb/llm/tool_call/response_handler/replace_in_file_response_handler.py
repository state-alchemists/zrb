import os
import tempfile
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.config.config import CFG
from zrb.llm.tool_call.args import parse_tool_args

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolCallPart
    from zrb.llm.ui.any_agent_output import AnyAgentOutput


async def replace_in_file_response_handler(
    ui: "AnyAgentOutput",
    call: "ToolCallPart",
    response: str,
    next_handler: Callable[["AnyAgentOutput", Any, str], Awaitable[Any]],
) -> Any:
    # lazy: zrb internal (heavy via transitive)
    from zrb.llm.agent.types import ToolApproved

    if call.tool_name != "Edit":
        return await next_handler(ui, call, response)

    if response.lower() not in ("e", "edit"):
        return await next_handler(ui, call, response)

    args = parse_tool_args(call)
    if args is None:
        return await next_handler(ui, call, response)

    old_text = args.get("old_text", "")
    new_text = args.get("new_text", "")

    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".old") as tf_old:
        tf_old.write(old_text)
        old_path = tf_old.name

    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".new") as tf_new:
        tf_new.write(new_text)
        new_path = tf_new.name

    try:
        cmd_tpl = CFG.DIFF_EDIT_COMMAND_TPL
        cmd = cmd_tpl.format(old=old_path, new=new_path)

        await ui.run_interactive_command(cmd, shell=True)

        with open(new_path, "r", encoding="utf-8") as f:
            edited_new_text = f.read()

        # Two-space indent, matching every other mid-turn status line printed
        # outside `StreamEventHandler` (see `web.py::_notify` and
        # `response_handler/default.py`) — without it these land at column 0.
        if edited_new_text != new_text:
            new_args = dict(args)
            new_args["new_text"] = edited_new_text
            ui.append_to_output("\n  ✅ Replacement modified.")
            return ToolApproved(override_args=new_args)
        else:
            ui.append_to_output("\n  ℹ️ No changes made.")
            return None

    except Exception as e:
        ui.append_to_output(f"\n  ❌ Error during diff edit: {e}")
        return None
    finally:
        if os.path.exists(old_path):
            os.remove(old_path)
        if os.path.exists(new_path):
            os.remove(new_path)
