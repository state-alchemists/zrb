from __future__ import annotations

import json
import os
import subprocess
import tempfile
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Protocol, TextIO

import yaml

from zrb.config.config import CFG
from zrb.util.cli.markdown import render_markdown
from zrb.util.yaml import yaml_dump

if TYPE_CHECKING:
    from pydantic_ai import ToolApproved, ToolCallPart, ToolDenied


class UIProtocol(Protocol):
    async def ask_user(self, prompt: str) -> str: ...

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ): ...


ConfirmationMiddleware = Callable[
    [
        UIProtocol,
        "ToolCallPart",
        str,
        Callable[[UIProtocol, "ToolCallPart", str], Awaitable[Any]],
    ],
    Awaitable[Any],
]


class ConfirmationHandler:
    def __init__(self, middlewares: list[ConfirmationMiddleware]):
        self._middlewares = middlewares

    def add_middleware(self, *middleware: ConfirmationMiddleware):
        self.prepend_middleware(*middleware)

    def prepend_middleware(self, *middleware: ConfirmationMiddleware):
        self._middlewares = list(middleware) + self._middlewares

    async def handle(
        self, ui: UIProtocol, call: ToolCallPart
    ) -> ToolApproved | ToolDenied | None:
        while True:
            message = self._get_confirm_user_message(call)
            ui.append_to_output(f"\n\n{message}", end="")
            # Wait for user input
            user_input = await ui.ask_user("")
            user_response = user_input.strip()

            # Build the chain
            async def _next(
                ui: UIProtocol, call: ToolCallPart, response: str, index: int
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

    def _get_confirm_user_message(self, call: ToolCallPart) -> str:
        args_section = ""
        if f"{call.args}" != "{}":
            args_str = self._format_args(call.args)
            args_section = f"{args_str}\n"
        return (
            f"  🎰 Executing tool '{call.tool_name}'\n"
            f"{args_section}"
            "  ❓ Allow tool Execution? (✅ Y | 🛑 n | ✏️ e)? "
        )

    def _format_args(self, args: Any) -> str:
        indent = " " * 7
        try:
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    pass
            args_str = yaml_dump(args)
            args_str = "\n".join([f"{indent}{line}" for line in args_str.splitlines()])
            width = None
            try:
                width = os.get_terminal_size().columns - len(indent) - 1
            except Exception:
                pass
            return render_markdown(f"```yaml\n{args_str}\n```", width=width)
        except Exception:
            return f"{indent}{args}"


async def last_confirmation(
    ui: UIProtocol,
    call: ToolCallPart,
    user_response: str,
    next_handler: Callable[[UIProtocol, ToolCallPart, str], Awaitable[Any]],
) -> ToolApproved | ToolDenied | None:
    from pydantic_ai import ToolApproved, ToolDenied

    print(user_response)

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

            new_content = await wait_edit_content(
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
