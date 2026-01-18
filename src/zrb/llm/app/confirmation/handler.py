import json
import os
import subprocess
import tempfile
from typing import Any, Awaitable, Callable, Protocol

import yaml

from zrb.config.config import CFG
from zrb.util.yaml import yaml_dump


class UIProtocol(Protocol):
    async def ask_user(self, prompt: str) -> str: ...

    def append_to_output(self, text: str, end: str = "\n"): ...


ConfirmationMiddleware = Callable[
    [UIProtocol, Any, str, Callable[[UIProtocol, Any, str], Awaitable[Any]]],
    Awaitable[Any],
]


class ConfirmationHandler:
    def __init__(self, middlewares: list[ConfirmationMiddleware]):
        self._middlewares = middlewares

    def add_middleware(self, *middleware: ConfirmationMiddleware):
        self.prepend_middleware(*middleware)

    def prepend_middleware(self, *middleware: ConfirmationMiddleware):
        self._middlewares = list(middleware) + self._middlewares

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
                if index >= len(self._middlewares):
                    # Default if no middleware handles it
                    return None
                middleware = self._middlewares[index]
                return await middleware(
                    ui,
                    call,
                    response,
                    lambda u, c, r: _next(u, c, r, index + 1),
                )

            result = await _next(ui, call, user_response, 0)
            if result is None:
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
            args_str = yaml_dump(args)
            # Indent nicely for display
            args_str = "\n".join(
                [f"{arg_line_prefix}{line}" for line in args_str.splitlines()]
            )
        except Exception:
            args_str = f"{arg_line_prefix}{call.args}"
        return (
            "  🎰 Executing tool '{tool_name}'\n"
            "       Arguments:\n{args_str}\n"
            "  ❓ Allow tool Execution? (✅ Y | 🛑 n | ✏️ e)? "
        ).format(tool_name=call.tool_name, args_str=args_str)


async def last_confirmation(
    ui: UIProtocol,
    call: Any,
    user_response: str,
    next_handler: Callable[[UIProtocol, Any, str], Awaitable[Any]],
) -> Any:
    from pydantic_ai import ToolApproved, ToolDenied

    if user_response.lower() in ("y", "yes", "ok", "okay", ""):
        ui.append_to_output("\n✅ Execution approved.")
        return ToolApproved()
    elif user_response.lower() in ("n", "no"):
        ui.append_to_output("\n🛑 Execution denied.")
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
                content = yaml_dump(args)
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
        return ToolDenied(f"User denied execution with message: {user_response}")


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
