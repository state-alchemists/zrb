from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Awaitable, Callable, TypeAlias, Union

from zrb.llm.agent.std_ui import StdUI
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
    from zrb.llm.tool_call.ui_protocol import UIProtocol

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


async def run_agent(
    agent: "Agent[None, Any]",
    message: str | None,
    message_history: list[Any],
    limiter: LLMLimiter,
    attachments: list[Any] | None = None,
    print_fn: Callable[[str], Any] = print,
    event_handler: Callable[[Any], Any] | None = None,
    tool_confirmation: AnyToolConfirmation = None,
    ui: UIProtocol | None = None,
) -> tuple[Any, list[Any]]:
    """
    Runs the agent with rate limiting, history management, and optional CLI confirmation loop.
    Returns (result_output, new_message_history).
    """
    from pydantic_ai import AgentRunResultEvent, DeferredToolRequests, UsageLimits

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

    # Resolve UI
    effective_ui = ui or StdUI()

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
                result_output, tool_confirmation, effective_ui, print_fn
            )
            if current_results is None:
                return result_output, run_history
            # Prepare next iteration
            current_message = None
            current_history = run_history
            continue
        return result_output, run_history


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
    ui: UIProtocol,
    print_fn: Callable[[str], Any] = print,
) -> "DeferredToolResults | None":
    """Handles tool approvals/denials via callback, ToolCallHandler, or CLI fallback."""
    import inspect

    from pydantic_ai import DeferredToolResults

    from zrb.llm.tool_call.handler import ToolCallHandler

    all_requests = (result_output.calls or []) + (result_output.approvals or [])
    if not all_requests:
        return None

    current_results = DeferredToolResults()

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
