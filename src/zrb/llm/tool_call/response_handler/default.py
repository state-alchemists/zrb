from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import yaml

from zrb.config.config import CFG
from zrb.context.any_context import zrb_print
from zrb.llm.tool_call.ui_protocol import UIProtocol
from zrb.util.yaml import yaml_dump

if TYPE_CHECKING:
    from pydantic_ai import ToolApproved, ToolCallPart, ToolDenied


async def default_response_handler(
    ui: UIProtocol,
    call: ToolCallPart,
    user_response: str,
    next_handler: Callable[[UIProtocol, ToolCallPart, str], Awaitable[Any]],
) -> ToolApproved | ToolDenied | None:
    from pydantic_ai import ToolApproved, ToolDenied

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

            # YAML for editing
            is_yaml_edit = True
            try:
                content = yaml_dump(args)
                extension = ".yaml"
            except Exception:
                # Fallback to JSON
                content = json.dumps(args, indent=2)
                extension = ".json"
                is_yaml_edit = False

            new_content = await _wait_edit_content(
                ui=ui,
                text_editor=CFG.EDITOR,
                content=content,
                extension=extension,
            )

            # Compare content
            if new_content == content:
                ui.append_to_output("\nℹ️ No changes made.")
                return None

            try:
                if is_yaml_edit:
                    new_args = yaml.safe_load(new_content)
                else:
                    new_args = json.loads(new_content)
                ui.append_to_output("\n✅ Execution approved (with modification).")
                return ToolApproved(override_args=new_args)
            except Exception as e:
                ui.append_to_output(f"\n❌ Invalid format: {e}. ", end="")
                # Return None to signal loop retry
                return None

        except Exception as e:
            ui.append_to_output(f"\n❌ Error editing: {e}. ", end="")
            return None
    else:
        ui.append_to_output("\n🛑 Execution denied.")
        ui.append_to_output(f"\n🛑 Reason: {user_response}")
        return ToolDenied(f"User denied execution with message: {user_response}")


async def _wait_edit_content(
    ui: UIProtocol,
    text_editor: str,
    content: str,
    extension: str = ".txt",
) -> str:
    # Write temporary file
    with tempfile.NamedTemporaryFile(suffix=extension, mode="w+", delete=False) as tf:
        tf.write(content)
        tf_path = tf.name

    # Edit and wait
    # We use run_interactive_command to ensure vim/editor has direct terminal access
    await ui.run_interactive_command([text_editor, tf_path], shell=False)
    with open(tf_path, "r") as tf:
        new_content = tf.read()
    os.remove(tf_path)

    return new_content
