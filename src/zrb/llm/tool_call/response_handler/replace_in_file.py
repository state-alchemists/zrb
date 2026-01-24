import json
import os
import tempfile
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from zrb.config.config import CFG
from zrb.llm.tool_call.ui_protocol import UIProtocol

if TYPE_CHECKING:
    from pydantic_ai import ToolCallPart


async def replace_in_file_response_handler(
    ui: UIProtocol,
    call: "ToolCallPart",
    response: str,
    next_handler: Callable[[UIProtocol, Any, str], Awaitable[Any]],
) -> Any:
    from pydantic_ai import ToolApproved

    if call.tool_name != "replace_in_file":
        return await next_handler(ui, call, response)

    if response.lower() not in ("e", "edit"):
        return await next_handler(ui, call, response)

    # It is replace_in_file and user wants to edit
    args = call.args
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            pass

    if not type(args) is dict:
        return await next_handler(ui, call, response)

    old_text = args.get("old_text", "")
    new_text = args.get("new_text", "")

    # Create temporary files
    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".old") as tf_old:
        tf_old.write(old_text)
        old_path = tf_old.name

    with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".new") as tf_new:
        tf_new.write(new_text)
        new_path = tf_new.name

    try:
        # Prepare command
        cmd_tpl = CFG.DIFF_EDIT_COMMAND_TPL
        cmd = cmd_tpl.format(old=old_path, new=new_path)

        # Run command using the UI's interactive command handler
        await ui.run_interactive_command(cmd, shell=True)

        # Read back new content
        with open(new_path, "r") as f:
            edited_new_text = f.read()

        if edited_new_text != new_text:
            # Update args
            new_args = dict(args)
            new_args["new_text"] = edited_new_text
            ui.append_to_output("\n✅ Replacement modified.")
            return ToolApproved(override_args=new_args)
        else:
            ui.append_to_output("\nℹ️ No changes made.")
            return None

    except Exception as e:
        ui.append_to_output(f"\n❌ Error during diff edit: {e}")
        return None
    finally:
        # Cleanup
        if os.path.exists(old_path):
            os.remove(old_path)
        if os.path.exists(new_path):
            os.remove(new_path)
