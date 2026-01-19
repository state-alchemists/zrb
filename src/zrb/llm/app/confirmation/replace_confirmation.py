import json
import os
import subprocess
import tempfile
from typing import Any, Awaitable, Callable

from prompt_toolkit.application import run_in_terminal

from zrb.config.config import CFG
from zrb.llm.app.confirmation.handler import UIProtocol


async def replace_confirmation(
    ui: UIProtocol,
    call: Any,
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
        cmd_tpl = CFG.DEFAULT_DIFF_EDIT_COMMAND_TPL
        cmd = cmd_tpl.format(old=old_path, new=new_path)

        # Run command
        await run_in_terminal(lambda: subprocess.call(cmd, shell=True))

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
