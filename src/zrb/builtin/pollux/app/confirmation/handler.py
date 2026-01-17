import json
import os
import subprocess
import tempfile
from typing import Any, Awaitable, Callable, Protocol

import yaml
from zrb.config.config import CFG


class UIProtocol(Protocol):
    async def ask_user(self, prompt: str) -> str: ...

    def append_to_output(self, text: str, end: str = "\n"): ...


ConfirmationMiddleware = Callable[
    [UIProtocol, Any, str, Callable[[UIProtocol, Any, str], Awaitable[Any]]],
    Awaitable[Any],
]


class ConfirmationHandler:
    def __init__(self, middlewares: list[ConfirmationMiddleware]):
        self.middlewares = middlewares

    async def handle(self, ui: UIProtocol, call: Any) -> Any:
        while True:
            message = self._get_confirm_user_message(call)
            ui.append_to_output(f"\n\n{message}", end="")
            # Wait for user input
            user_input = await ui.ask_user("")
            user_response = user_input.strip()

            # Build the chain
            async def _next(
                ui: UIProtocol, call: Any, response: str, index: int
            ) -> Any:
                if index >= len(self.middlewares):
                    # Default if no middleware handles it
                    return None
                middleware = self.middlewares[index]
                return await middleware(
                    ui,
                    call,
                    response,
                    lambda u, c, r: _next(u, c, r, index + 1),
                )

            result = await _next(ui, call, user_response, 0)
            # If result is None, it means no middleware handled it (invalid choice likely)
            if result is None:
                ui.append_to_output("\n  ⛔ Invalid choice. ", end="")
                continue
            return result

    def _get_confirm_user_message(self, call: Any):
        arg_line_prefix = " " * 7
        try:
            args = call.args
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    pass
            args_str = yaml.dump(args, default_flow_style=False, sort_keys=False)
            # Indent nicely for display
            args_str = "\n".join(
                [f"{arg_line_prefix}{line}" for line in args_str.splitlines()]
            )
        except Exception:
            args_str = f"{arg_line_prefix}{call.args}"
        return "\n".join(
            [
                f"  ❓ Execute tool '{call.tool_name}'?",
                f"     Arguments:\n{args_str}",
                "     (y/n/e) ",
            ]
        )


async def last_confirmation(
    ui: UIProtocol,
    call: Any,
    user_response: str,
    next_handler: Callable[[UIProtocol, Any, str], Awaitable[Any]],
) -> Any:
    from pydantic_ai import ToolApproved, ToolDenied

    if user_response.lower() in ("y", "yes", "ok", "okay", ""):
        return ToolApproved()
    elif user_response.lower() in ("n", "no"):
        return ToolDenied("User denied execution")
    elif user_response.lower() in ("e", "edit"):
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
                content = yaml.dump(args, default_flow_style=False, sort_keys=False)
                extension = ".yaml"
            except Exception:
                # Fallback to JSON
                content = json.dumps(args, indent=2)
                extension = ".json"
                is_yaml_edit = False

            new_content = await wait_edit_content(
                text_editor=CFG.DEFAULT_EDITOR,
                content=content,
                extension=extension,
            )

            # Compare content
            if new_content == content:
                return None

            try:
                if is_yaml_edit:
                    new_args = yaml.safe_load(new_content)
                else:
                    new_args = json.loads(new_content)
                return ToolApproved(override_args=new_args)
            except Exception as e:
                ui.append_to_output(f"\n❌ Invalid format: {e}. ", end="")
                # Return None to signal loop retry
                return None

        except Exception as e:
            ui.append_to_output(f"\n❌ Error editing: {e}. ", end="")
            return None
    else:
        return ToolDenied(f"User denied execution: {user_response}")


async def wait_edit_content(
    text_editor: str, content: str, extension: str = ".txt"
) -> str:
    from prompt_toolkit.application import run_in_terminal

    # Write temporary file
    with tempfile.NamedTemporaryFile(suffix=extension, mode="w+", delete=False) as tf:
        tf.write(content)
        tf_path = tf.name

    # Edit and wait
    await run_in_terminal(lambda: subprocess.call([text_editor, tf_path]))
    with open(tf_path, "r") as tf:
        new_content = tf.read()
    os.remove(tf_path)

    return new_content
