from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from zrb.llm.tool_call.judge_note import format_judge_line
from zrb.llm.tool_call.middleware import (
    ArgumentFormatter,
    ResponseHandler,
    ToolPolicy,
)
from zrb.llm.util.tool_args import parse_tool_args_value, read_purpose, without_purpose
from zrb.util.cli.markdown import render_markdown
from zrb.util.truncate import truncate_chars, truncate_display
from zrb.util.yaml import yaml_dump

if TYPE_CHECKING:
    from zrb.llm.agent.types import ToolApproved, ToolCallPart, ToolDenied
    from zrb.llm.ui.any_agent_output import AnyAgentOutput

# A denial reason is a short human-typed note. Clamp it so a mis-submitted
# payload (e.g. a whole screen buffer) can never enter the conversation
# history as a tool result.
MAX_DENIAL_REASON_CHARS = 500

# What a user types at an approval prompt to approve or deny, case-insensitively.
APPROVE_RESPONSES = frozenset({"y", "yes", "ok", "accept", "✅", ""})
DENY_RESPONSES = frozenset({"n", "no", "deny", "cancel", "🛑"})

# A purpose is one short phrase. A model that writes a paragraph into it would
# otherwise push the arguments it is meant to introduce off the screen.
MAX_PURPOSE_CHARS = 200


def format_purpose_line(purpose: str | None) -> str:
    """*purpose* as one indented line of the prompt, or `""` for none.

    One line on purpose: a purpose spread over several would read as part of
    the arguments below it, and a control character could rewrite the prompt
    the user is about to answer.
    """
    if not purpose:
        return ""
    printable = "".join(char if char.isprintable() else " " for char in purpose)
    shown = " ".join(printable.split())
    if not shown:
        return ""
    return f"       🎯 {truncate_display(shown, MAX_PURPOSE_CHARS)}\n"


async def check_tool_policies(
    policies: list[ToolPolicy],
    ui: AnyAgentOutput,
    call: ToolCallPart,
) -> ToolApproved | ToolDenied | None:
    async def _next_policy(ui: AnyAgentOutput, call: ToolCallPart, index: int) -> Any:
        if index >= len(policies):
            return None
        policy = policies[index]
        return await policy(
            ui,
            call,
            lambda u, c: _next_policy(u, c, index + 1),
        )

    return await _next_policy(ui, call, 0)


async def run_response_handlers(
    handlers: list[ResponseHandler],
    ui: AnyAgentOutput,
    call: ToolCallPart,
    response: str,
    fallback: Callable[[AnyAgentOutput, ToolCallPart, str], Awaitable[Any]],
) -> Any:
    """Offer *response* to each handler in order; *fallback* answers when all pass."""

    async def _next_handler(
        ui: AnyAgentOutput, call: ToolCallPart, response: str, index: int
    ) -> Any:
        if index >= len(handlers):
            return await fallback(ui, call, response)
        return await handlers[index](
            ui, call, response, lambda u, c, r: _next_handler(u, c, r, index + 1)
        )

    return await _next_handler(ui, call, response, 0)


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

    def prepend_tool_policy(self, *policy: ToolPolicy):
        self._tool_policies = list(policy) + self._tool_policies

    def prepend_argument_formatter(self, *formatter: ArgumentFormatter):
        self._argument_formatters = list(formatter) + self._argument_formatters

    def prepend_response_handler(self, *handler: ResponseHandler):
        self._response_handlers = list(handler) + self._response_handlers

    async def handle(
        self,
        ui: AnyAgentOutput,
        call: ToolCallPart,
    ) -> ToolApproved | ToolDenied | None:
        # lazy: zrb internal (heavy via transitive)
        from zrb.llm.agent.types import ToolApproved, ToolDenied

        async def answer_by_vocabulary(
            ui: AnyAgentOutput, call: ToolCallPart, response: str
        ) -> ToolApproved | ToolDenied:
            r = response.lower().strip()
            if r in APPROVE_RESPONSES:
                return ToolApproved()
            if r in DENY_RESPONSES:
                return ToolDenied("User denied")
            reason = truncate_chars(response, MAX_DENIAL_REASON_CHARS)
            return ToolDenied(f"User denied execution with message: {reason}")

        policy_result = await self.check_policies(ui, call)
        if policy_result is not None:
            return policy_result

        while True:
            message = await self.format_approval_message(ui, call)
            ui.append_to_output(f"\n{message}", end="")
            user_input = await ui.input.ask_user("", output_to_parent=f"\n{message}")
            result = await run_response_handlers(
                self._response_handlers,
                ui,
                call,
                user_input.strip(),
                answer_by_vocabulary,
            )
            if result is None:
                continue
            return result

    async def check_policies(
        self,
        ui: AnyAgentOutput,
        call: ToolCallPart,
    ) -> ToolApproved | ToolDenied | None:
        return await check_tool_policies(self._tool_policies, ui, call)

    async def format_approval_message(
        self,
        ui: AnyAgentOutput,
        call: ToolCallPart,
        approval_instruction: str | None = None,
    ) -> str:
        """Format the approval request message for a tool call.

        The call's ``purpose`` gets a line of its own, above the arguments and
        outside the section a formatter may replace: it says what the call is
        *for*, which is what the person answering needs first, and `Shell`,
        `Write` and `Edit` each show a body of their own that would drop it. It
        is taken out of the arguments below, so the prompt says it once.

        The shell judge's verdict gets the next line, drawn the same way and for
        the same reason: it is decided in ``agent/run/deferred_calls.py``, which
        reaches this method only through ``tool_call_id`` (ADR-0141).
        """
        args = parse_tool_args_value(call.args)
        display_args = without_purpose(args) if args is not None else call.args
        args_section = ""
        if f"{display_args}" != "{}":
            # Blocking CPU (~700ms on a large Write); inline it freezes the TUI.
            args_str = await asyncio.to_thread(self._format_args, display_args)
            args_section = f"{args_str}\n"

        for formatter in self._argument_formatters:
            new_args_section = await formatter(ui, call, args_section)
            if new_args_section is not None:
                args_section = new_args_section

        instruction = (
            approval_instruction or "  ❓ Allow tool Execution? (✅ Y | 🛑 n | 📝 e)? "
        )

        return (
            f"  🎰 Executing tool '{call.tool_name}'\n"
            f"{format_purpose_line(read_purpose(call.args))}"
            f"{format_judge_line(call.tool_call_id)}"
            f"{args_section}"
            f"{instruction}"
        )

    def get_response_handlers(self) -> list[ResponseHandler]:
        """Response handlers, for approval channels that delegate to them."""
        return self._response_handlers

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
            return render_markdown(f"```yaml\n{args_str}\n```", width=None)
        except Exception:
            return f"{indent}{args}"
