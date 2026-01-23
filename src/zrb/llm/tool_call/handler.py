from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

from zrb.llm.tool_call.middleware import (
    ArgumentFormatter,
    ResponseHandler,
    ToolPolicy,
)
from zrb.llm.tool_call.ui_protocol import UIProtocol
from zrb.util.cli.markdown import render_markdown
from zrb.util.yaml import yaml_dump

if TYPE_CHECKING:
    from pydantic_ai import ToolApproved, ToolCallPart, ToolDenied


async def check_tool_policies(
    policies: list[ToolPolicy],
    ui: UIProtocol,
    call: ToolCallPart,
) -> ToolApproved | ToolDenied | None:
    async def _next_policy(ui: UIProtocol, call: ToolCallPart, index: int) -> Any:
        if index >= len(policies):
            return None
        policy = policies[index]
        return await policy(
            ui,
            call,
            lambda u, c: _next_policy(u, c, index + 1),
        )

    return await _next_policy(ui, call, 0)


class ToolCallHandler:
    def __init__(
        self,
        tool_policies: list[ToolPolicy] | None = None,
        argument_formatters: list[ArgumentFormatter] | None = None,
        response_handlers: list[ResponseHandler] | None = None,
    ):
        self._tool_policies = tool_policies or []
        self._argument_formatters = argument_formatters or []
        self._response_handlers = response_handlers or []

    def add_tool_policy(self, *policy: ToolPolicy):
        self.prepend_tool_policy(*policy)

    def prepend_tool_policy(self, *policy: ToolPolicy):
        self._tool_policies = list(policy) + self._tool_policies

    def add_argument_formatter(self, *formatter: ArgumentFormatter):
        self.prepend_argument_formatter(*formatter)

    def prepend_argument_formatter(self, *formatter: ArgumentFormatter):
        self._argument_formatters = list(formatter) + self._argument_formatters

    def add_response_handler(self, *handler: ResponseHandler):
        self.prepend_response_handler(*handler)

    def prepend_response_handler(self, *handler: ResponseHandler):
        self._response_handlers = list(handler) + self._response_handlers

    async def handle(
        self,
        ui: UIProtocol,
        call: ToolCallPart,
    ) -> ToolApproved | ToolDenied | None:
        # Tool Policies (Pre-confirmation)
        policy_result = await self.check_policies(ui, call)
        if policy_result is not None:
            return policy_result

        while True:
            message = await self._get_confirm_user_message(ui, call)
            ui.append_to_output(f"\n\n{message}", end="")
            # Wait for user input
            user_input = await ui.ask_user("")
            user_response = user_input.strip()

            # Response Handlers (Post-confirmation)
            async def _next_handler(
                ui: UIProtocol,
                call: ToolCallPart,
                response: str,
                index: int,
            ) -> Any:
                if index >= len(self._response_handlers):
                    # Default behavior: simple y/n check
                    r = response.lower().strip()
                    if r in ("y", "yes", "ok", "accept", "✅"):
                        from pydantic_ai import ToolApproved

                        return ToolApproved()
                    if r in ("n", "no", "deny", "cancel", "🛑"):
                        from pydantic_ai import ToolDenied

                        return ToolDenied("User denied")
                    return None

                handler = self._response_handlers[index]
                return await handler(
                    ui,
                    call,
                    response,
                    lambda u, c, r: _next_handler(u, c, r, index + 1),
                )

            result = await _next_handler(ui, call, user_response, 0)
            if result is None:
                continue
            return result

    async def check_policies(
        self,
        ui: UIProtocol,
        call: ToolCallPart,
    ) -> ToolApproved | ToolDenied | None:
        return await check_tool_policies(self._tool_policies, ui, call)

    async def _get_confirm_user_message(
        self,
        ui: UIProtocol,
        call: ToolCallPart,
    ) -> str:
        args_section = ""
        if f"{call.args}" != "{}":
            args_str = self._format_args(call.args)
            args_section = f"{args_str}\n"

        for formatter in self._argument_formatters:
            new_args_section = await formatter(ui, call, args_section)
            if new_args_section is not None:
                args_section = new_args_section

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
