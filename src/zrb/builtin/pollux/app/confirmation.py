import json
import os
import subprocess
import tempfile
from typing import Any, Awaitable, Callable, Protocol

import yaml
from prompt_toolkit.application import run_in_terminal
from pydantic_ai import ToolApproved, ToolDenied


class UIProtocol(Protocol):
    async def ask_user(self, prompt: str) -> str: ...
    def append_to_output(self, text: str, end: str = "\n"): ...


class ConfirmationMiddleware(Protocol):
    async def __call__(
        self,
        ui: UIProtocol,
        call: Any,
        next_handler: Callable[[Any], Awaitable[Any]],
    ) -> Any: ...


class ConfirmationHandler:
    def __init__(self, middlewares: list[ConfirmationMiddleware]):
        self.middlewares = middlewares

    async def handle(self, ui: UIProtocol, call: Any) -> Any:
        # Build the chain
        async def _next(call: Any, index: int) -> Any:
            if index >= len(self.middlewares):
                # Default if no middleware handles it (shouldn't happen with Interactive as last)
                return ToolDenied("No middleware handled the confirmation.")

            middleware = self.middlewares[index]
            return await middleware(
                ui,
                call,
                lambda c: _next(c, index + 1),
            )

        return await _next(call, 0)


class InteractiveConfirmationMiddleware:
    async def __call__(
        self,
        ui: UIProtocol,
        call: Any,
        next_handler: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        while True:
            # Format args nicely (YAML-like)
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
                    ["       " + line for line in args_str.splitlines()]
                )
            except Exception:
                args_str = f"       {call.args}"

            message = f"Execute tool '{call.tool_name}'?\n     Arguments:\n{args_str}"

            # Prompt
            ui.append_to_output(f"\n\n  ❓ {message}\n   (y/n/e) ", end="")

            # Wait for user input
            user_input = await ui.ask_user("")
            choice = user_input.strip().lower()

            if choice in ("y", "yes"):
                return ToolApproved()
            elif choice in ("n", "no"):
                return ToolDenied("User denied execution")
            elif choice in ("e", "edit"):
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
                        content = yaml.dump(
                            args, default_flow_style=False, sort_keys=False
                        )
                        suffix = ".yaml"
                    except Exception:
                        # Fallback to JSON
                        content = json.dumps(args, indent=2)
                        suffix = ".json"
                        is_yaml_edit = False

                    with tempfile.NamedTemporaryFile(
                        suffix=suffix, mode="w+", delete=False
                    ) as tf:
                        tf.write(content)
                        tf_path = tf.name

                    editor = os.environ.get("EDITOR", "vim")

                    await run_in_terminal(lambda: subprocess.call([editor, tf_path]))

                    with open(tf_path, "r") as tf:
                        new_content = tf.read()
                    os.remove(tf_path)

                    try:
                        if is_yaml_edit:
                            new_args = yaml.safe_load(new_content)
                        else:
                            new_args = json.loads(new_content)
                        return ToolApproved(override_args=new_args)
                    except Exception as e:
                        ui.append_to_output(
                            f"\n❌ Invalid format: {e}. Try again? ", end=""
                        )
                        continue

                except Exception as e:
                    ui.append_to_output(f"\n❌ Error editing: {e}. ", end="")
                    continue
            else:
                ui.append_to_output("\nInvalid choice. ", end="")
