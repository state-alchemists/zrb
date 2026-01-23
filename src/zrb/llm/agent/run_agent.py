from __future__ import annotations

import asyncio
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Awaitable, Callable, TextIO, TypeAlias, Union

from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.util.attachment import normalize_attachments
from zrb.llm.util.prompt import expand_prompt

if TYPE_CHECKING:
    from pydantic_ai import (
        Agent,
        DeferredToolRequests,
        DeferredToolResults,
        ToolApproved,
        ToolCallPart,
        ToolDenied,
    )
    from pydantic_ai.messages import UserPromptPart

    from zrb.llm.tool_call.handler import ToolCallHandler

    AnyToolConfirmation: TypeAlias = Union[
        Callable[
            [ToolCallPart],
            ToolApproved | ToolDenied | Awaitable[ToolApproved | ToolDenied],
        ],
        ToolCallHandler,
        None,
    ]
else:
    AnyToolConfirmation: TypeAlias = Any

# Context variable to propagate tool confirmation callback to sub-agents
tool_confirmation_var: ContextVar[AnyToolConfirmation] = ContextVar(
    "tool_confirmation", default=None
)


class StdUI:
    """Standard UI implementation of UIProtocol for terminal environments."""

    async def ask_user(self, prompt: str) -> str:
        """Prompt user via CLI input."""
        import sys

        if prompt:
            sys.stderr.write(prompt)
            sys.stderr.flush()

        # Use asyncio.to_thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        user_input = await loop.run_in_executor(None, input, "")
        return user_input.strip()

    def append_to_output(
        self,
        *values: object,
        sep: str = " ",
        end: str = "\n",
        file: TextIO | None = None,
        flush: bool = False,
    ):
        """Print output to stderr."""
        import sys

        # Always print to stderr as per requirements
        print(*values, sep=sep, end=end, file=sys.stderr, flush=flush)

    async def run_interactive_command(
        self, cmd: str | list[str], shell: bool = False
    ) -> Any:
        """Run interactive commands using subprocess."""
        import subprocess

        def _run():
            return subprocess.run(cmd, shell=shell)

        return await asyncio.to_thread(_run)


async def run_agent(
    agent: "Agent[None, Any]",
    message: str | None,
    message_history: list[Any],
    limiter: LLMLimiter,
    attachments: list[Any] | None = None,
    print_fn: Callable[[str], Any] = print,
    event_handler: Callable[[Any], Any] | None = None,
    tool_confirmation: AnyToolConfirmation = None,
) -> tuple[Any, list[Any]]:
    """
    Runs the agent with rate limiting, history management, and optional CLI confirmation loop.
    Returns (result_output, new_message_history).
    """
    import asyncio

    from pydantic_ai import AgentRunResultEvent, DeferredToolRequests, UsageLimits

    # Resolve tool confirmation callback (Arg > Context > None)
    effective_tool_confirmation = tool_confirmation
    if effective_tool_confirmation is None:
        effective_tool_confirmation = tool_confirmation_var.get()

    # Set context var for sub-agents
    token = tool_confirmation_var.set(effective_tool_confirmation)

    try:
        # Expand user message with references
        effective_message = expand_prompt(message) if message else message

        # Prepare Prompt Content
        prompt_content = _get_prompt_content(effective_message, attachments, print_fn)

        # 1. Prune & Throttle
        current_history = await _acquire_rate_limit(
            limiter, prompt_content, message_history, print_fn
        )
        current_message = prompt_content
        current_results = None

        # 2. Execution Loop
        while True:
            result_output = None
            run_history = []

            async for event in agent.run_stream_events(
                current_message,
                message_history=current_history,
                deferred_tool_results=current_results,
                usage_limits=UsageLimits(request_limit=None),
            ):
                await asyncio.sleep(0)
                if isinstance(event, AgentRunResultEvent):
                    result = event.result
                    result_output = result.output
                    run_history = result.all_messages()
                if event_handler:
                    await event_handler(event)

            # Handle Deferred Calls
            if isinstance(result_output, DeferredToolRequests):
                current_results = await _process_deferred_requests(
                    result_output, effective_tool_confirmation, print_fn
                )
                if current_results is None:
                    return result_output, run_history
                # Prepare next iteration
                current_message = None
                current_history = run_history
                continue
            return result_output, run_history
    finally:
        tool_confirmation_var.reset(token)


def _get_prompt_content(
    message: str | None, attachments: list[Any] | None, print_fn: Callable[[str], Any]
) -> "list[UserPromptPart] | str | None":
    from pydantic_ai.messages import UserPromptPart

    prompt_content = message
    if attachments:
        attachments = normalize_attachments(attachments, print_fn)
        parts: list[UserPromptPart] = []
        if message:
            parts.append(UserPromptPart(content=message))
        parts.extend(attachments)
        prompt_content = parts
    return prompt_content


async def _acquire_rate_limit(
    limiter: LLMLimiter,
    message: str | None,
    message_history: list[Any],
    print_fn: Callable[[str], Any],
) -> list[Any]:
    """Prunes history and waits if rate limits are exceeded."""
    if not message:
        return message_history

    # Prune
    pruned_history = limiter.fit_context_window(message_history, message)

    # Throttle
    est_tokens = limiter.count_tokens(pruned_history) + limiter.count_tokens(message)
    await limiter.acquire(
        est_tokens, notifier=lambda msg: print_fn(msg) if msg else None
    )

    return pruned_history


async def _process_deferred_requests(
    result_output: "DeferredToolRequests",
    effective_tool_confirmation: AnyToolConfirmation,
    print_fn: Callable[[str], Any] = print,
) -> "DeferredToolResults | None":
    """Handles tool approvals/denials via callback, ToolCallHandler, or CLI fallback."""
    import asyncio
    import inspect

    from pydantic_ai import DeferredToolResults, ToolApproved, ToolDenied

    from zrb.llm.tool_call.handler import ToolCallHandler

    all_requests = (result_output.calls or []) + (result_output.approvals or [])
    if not all_requests:
        return None

    current_results = DeferredToolResults()
    ui = StdUI()

    for call in all_requests:
        result = None
        handled = False

        if effective_tool_confirmation:
            if isinstance(effective_tool_confirmation, ToolCallHandler):
                result = await effective_tool_confirmation.handle(ui, call)
            else:
                # It's a simple callback function (or object with __call__)
                # If it returns None, it means "I don't know", so we fallback to CLI
                res = effective_tool_confirmation(call)
                if inspect.isawaitable(res):
                    result = await res
                else:
                    result = res

            if result is not None:
                handled = True

        if handled:
            current_results.approvals[call.tool_call_id] = result
        else:
            # CLI Fallback using StdUI logic
            handler = ToolCallHandler()  # Use default handler with no policies
            result = await handler.handle(ui, call)
            current_results.approvals[call.tool_call_id] = result

    return current_results
