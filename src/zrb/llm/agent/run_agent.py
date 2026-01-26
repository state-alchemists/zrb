from __future__ import annotations

import asyncio
from contextvars import ContextVar
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


current_ui: ContextVar[UIProtocol | None] = ContextVar("current_ui", default=None)
current_tool_confirmation: ContextVar[AnyToolConfirmation] = ContextVar(
    "current_tool_confirmation", default=None
)


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

    # Resolve UI and Tool Confirmation from arguments or context fallback
    effective_ui = ui or current_ui.get() or StdUI()
    effective_tool_confirmation = tool_confirmation or current_tool_confirmation.get()

    # Set context variables so sub-agents can inherit them
    token_ui = current_ui.set(effective_ui)
    token_confirmation = current_tool_confirmation.set(effective_tool_confirmation)

    try:
        # Resolve print_fn and event_handler for streaming visibility
        effective_print_fn = print_fn
        # If using default print but we have a UI, redirect to UI
        if effective_print_fn == print and effective_ui:
            effective_print_fn = effective_ui.append_to_output

        effective_event_handler = event_handler
        if effective_event_handler is None:
            from zrb.config.config import CFG
            from zrb.llm.util.stream_response import (
                create_event_handler,
                create_faint_printer,
            )

            print_event = create_faint_printer(effective_print_fn)
            effective_event_handler = create_event_handler(
                print_event,
                show_tool_call_detail=CFG.LLM_SHOW_TOOL_CALL_DETAIL,
                show_tool_result=CFG.LLM_SHOW_TOOL_CALL_RESULT,
            )

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
                if effective_event_handler:
                    await effective_event_handler(event)

            # Handle Deferred Calls
            if isinstance(result_output, DeferredToolRequests):
                current_results = await _process_deferred_requests(
                    result_output,
                    effective_tool_confirmation,
                    effective_ui,
                )
                if current_results is None:
                    return result_output, run_history
                # Prepare next iteration
                current_message = None
                current_history = run_history
                continue
            return result_output, run_history
    finally:
        # Restore context variables
        current_ui.reset(token_ui)
        current_tool_confirmation.reset(token_confirmation)


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
    print_fn: Callable[..., Any],
) -> list[Any]:
    """Prunes history and waits if rate limits are exceeded."""

    def notify_throtling(msg: str):
        if not msg:
            # Clear line
            try:
                print_fn("\r\033[K", end="")
            except TypeError:
                pass
            return
        # Print waiting message
        try:
            print_fn(f"\r{msg}", end="")
        except TypeError:
            print_fn(msg)

    if not message:
        return message_history
    # Prune history
    pruned_history = limiter.fit_context_window(message_history, message)
    # Throttle
    await limiter.acquire(
        {"message": message, "history": pruned_history},
        notifier=notify_throtling,
    )
    return pruned_history


async def _process_deferred_requests(
    result_output: "DeferredToolRequests",
    effective_tool_confirmation: AnyToolConfirmation,
    ui: UIProtocol,
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
