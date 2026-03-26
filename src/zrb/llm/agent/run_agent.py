from __future__ import annotations

import asyncio
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Awaitable, Callable, TypeAlias, Union

from zrb.llm.approval.approval_channel import ApprovalChannel, current_approval_channel
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.manager import hook_manager as default_hook_manager
from zrb.llm.hook.types import HookEvent
from zrb.llm.message import ensure_alternating_roles
from zrb.llm.tool_call.handler import ToolCallHandler
from zrb.llm.tool_call.ui_protocol import UIProtocol
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
current_hook_manager: ContextVar[HookManager | None] = ContextVar(
    "current_hook_manager", default=None
)
current_yolo: ContextVar[bool] = ContextVar("current_yolo", default=False)


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
    hook_manager: HookManager | None = None,
    yolo: bool = False,
    approval_channel: "ApprovalChannel | None" = None,
) -> tuple[Any, list[Any]]:
    """
    Runs the agent with rate limiting, history management, and optional CLI confirmation loop.
    Returns (result_output, new_message_history).
    """
    from pydantic_ai import AgentRunResultEvent, DeferredToolRequests, UsageLimits

    from zrb.llm.agent.std_ui import StdUI

    # Resolve UI, Tool Confirmation, Hook Manager, YOLO, and Approval Channel from arguments or context fallback
    effective_ui = ui or current_ui.get() or StdUI()
    effective_tool_confirmation = tool_confirmation or current_tool_confirmation.get()
    effective_hook_manager = (
        hook_manager or current_hook_manager.get() or default_hook_manager
    )
    effective_yolo = yolo or current_yolo.get()
    effective_approval_channel = approval_channel or current_approval_channel.get()

    # Set context variables so sub-agents can inherit them
    token_ui = current_ui.set(effective_ui)
    token_confirmation = current_tool_confirmation.set(effective_tool_confirmation)
    token_hook_manager = current_hook_manager.set(effective_hook_manager)
    token_yolo = current_yolo.set(effective_yolo)
    token_approval_channel = current_approval_channel.set(effective_approval_channel)

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
            # For status events (tool calls, results), use stream_to_parent if available
            # to bypass buffering in subagents (BufferedUI)
            status_fn = None
            if effective_ui and hasattr(effective_ui, "stream_to_parent"):
                status_fn = create_faint_printer(effective_ui.stream_to_parent)
            effective_event_handler = create_event_handler(
                print_event,
                show_tool_call_detail=CFG.LLM_SHOW_TOOL_CALL_DETAIL,
                show_tool_result=CFG.LLM_SHOW_TOOL_CALL_RESULT,
                status_event=status_fn,
            )

        # Hook: SessionStart
        await effective_hook_manager.execute_hooks(
            HookEvent.SESSION_START,
            {
                "message": message,
                "history": message_history,
                "attachments": attachments,
            },
        )

        # Expand user message with references
        effective_message = expand_prompt(message) if message else message

        # Hook: UserPromptSubmit
        await effective_hook_manager.execute_hooks(
            HookEvent.USER_PROMPT_SUBMIT,
            {
                "original_message": message,
                "expanded_message": effective_message,
                "attachments": attachments,
            },
        )

        # Prepare Prompt Content
        prompt_content = _get_prompt_content(effective_message, attachments, print_fn)

        # 1. Prune & Throttle
        # Hook: PreCompact - invoked before history processing/summarization
        await effective_hook_manager.execute_hooks(
            HookEvent.PRE_COMPACT,
            {
                "history": message_history,
                "token_count": limiter.count_tokens(message_history),
                "message_count": len(message_history),
                "has_history_processors": hasattr(agent, "history_processors"),
            },
        )

        # Process history first (e.g. summarization)
        processed_history = message_history
        if hasattr(agent, "history_processors"):
            for processor in agent.history_processors:
                processed_history = await processor(processed_history)

        # Safety Check: Ensure alternating roles in history
        processed_history = ensure_alternating_roles(processed_history)

        # EMERGENCY FAILSAFE: If summarization failed to reduce size below limit
        # (e.g. resulted in a 1M token summary), we must hard-prune to avoid API crash.
        current_tokens = limiter.count_tokens(processed_history)
        if current_tokens > limiter.max_token_per_request:
            print_fn(
                f"\n[System] History too large ({current_tokens} tokens) after summarization. Force pruning..."
            )
            # Keep only the last message (User prompt) if possible, or clear all if even that is too big
            # Ideally we keep system prompt + last user message
            safe_history = []
            # preserve system prompt if it exists (usually it's not in message_history for pydantic_ai, but just in case)
            # For now, just keep the very last message if it fits
            if (
                processed_history
                and limiter.count_tokens(processed_history[-1])
                < limiter.max_token_per_request
            ):
                safe_history = [processed_history[-1]]
            processed_history = safe_history

        current_history = await _acquire_rate_limit(
            limiter, prompt_content, processed_history, print_fn
        )
        current_message = prompt_content
        current_results = None

        # 2. Safety Check: Merge consecutive ModelRequest if needed
        # (e.g. if history was summarized and ends with a ModelRequest)
        from pydantic_ai.messages import ModelRequest

        if (
            current_history
            and isinstance(current_history[-1], ModelRequest)
            and current_message is not None
        ):
            # Convert current_message to list of parts if it's just a string
            from pydantic_ai.messages import UserPromptPart

            new_parts: list[UserPromptPart] = []
            if isinstance(current_message, str):
                new_parts = [UserPromptPart(content=current_message)]
            elif isinstance(current_message, list):
                new_parts = current_message

            # Merge into the last request and set current_message to None
            # so pydantic_ai doesn't add another request
            current_history[-1].parts.extend(new_parts)
            current_message = None

        # 3. Execution Loop
        run_history = current_history
        result_output = None
        stream = None
        try:
            while True:
                stream = agent.run_stream_events(
                    current_message,
                    message_history=current_history,
                    deferred_tool_results=current_results,
                    usage_limits=UsageLimits(request_limit=None),
                )
                try:
                    async for event in stream:
                        await asyncio.sleep(0)
                        if isinstance(event, AgentRunResultEvent):
                            result = event.result
                            result_output = result.output
                            run_history = result.all_messages()
                        if effective_event_handler:
                            await effective_event_handler(event)
                finally:
                    # Ensure stream is closed on cancellation or completion
                    if stream is not None and hasattr(stream, "aclose"):
                        await stream.aclose()

                # Handle Deferred Calls
                if isinstance(result_output, DeferredToolRequests):
                    current_results = await _process_deferred_requests(
                        result_output,
                        effective_tool_confirmation,
                        effective_ui,
                        effective_hook_manager,
                        effective_approval_channel,
                    )
                    if current_results is None:
                        # Hook: SessionEnd (premature end due to tool denial or wait)
                        await effective_hook_manager.execute_hooks(
                            HookEvent.SESSION_END,
                            {"reason": "deferred_wait", "history": run_history},
                        )
                        return result_output, run_history
                    # Prepare next iteration
                    current_message = None
                    current_history = run_history
                    continue

                # Hook: SessionEnd
                await effective_hook_manager.execute_hooks(
                    HookEvent.SESSION_END,
                    {"output": result_output, "history": run_history},
                )

                return result_output, run_history
        except asyncio.CancelledError:
            # Propagate cancellation to allow proper cleanup
            raise
        except Exception as e:
            if not hasattr(e, "zrb_history"):
                setattr(e, "zrb_history", run_history)
            raise e
    finally:
        # Restore context variables
        current_ui.reset(token_ui)
        current_tool_confirmation.reset(token_confirmation)
        current_hook_manager.reset(token_hook_manager)
        current_yolo.reset(token_yolo)
        current_approval_channel.reset(token_approval_channel)


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
    hook_manager: HookManager,
    approval_channel: "ApprovalChannel | None" = None,
) -> "DeferredToolResults | None":
    """Handles tool approvals/denials via policy, approval channel, or CLI fallback.

    Priority order:
    1. Tool confirmation handler (if provided) - for policy-based approval
    2. Approval channel (if provided) - for remote/external approval
    3. CLI fallback via ToolCallHandler with UI.ask_user()
    """
    import inspect

    from pydantic_ai import DeferredToolResults, ToolDenied

    from zrb.llm.approval.approval_channel import ApprovalContext
    from zrb.llm.tool_call.handler import ToolCallHandler

    all_requests = (result_output.calls or []) + (result_output.approvals or [])
    if not all_requests:
        return None

    current_results = DeferredToolResults()

    for call in all_requests:
        # Hook: PreToolUse
        hook_results = await hook_manager.execute_hooks(
            HookEvent.PRE_TOOL_USE,
            {"tool": call.tool_name, "args": call.args, "call_id": call.tool_call_id},
        )
        # Apply modifications from hooks (simple args merging for now)
        for hr in hook_results:
            if hr.modifications.get("tool_args"):
                if isinstance(call.args, dict):
                    call.args.update(hr.modifications["tool_args"])
            if hr.modifications.get("cancel_tool"):
                current_results.approvals[call.tool_call_id] = ToolDenied(
                    "Tool execution cancelled by hook"
                )
                continue

        result = None
        handled = False

        # Priority 1: Tool Confirmation Handler (policy-based approval)
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

            # If policy made a decision (not None), we're done
            if result is not None:
                handled = True

        # Priority 2: Approval Channel (remote/external approval)
        if not handled and approval_channel is not None:
            context = ApprovalContext(
                tool_name=call.tool_name,
                tool_args=call.args if isinstance(call.args, dict) else {},
                tool_call_id=call.tool_call_id,
            )
            approval_result = await approval_channel.request_approval(context)
            result = approval_result.to_pydantic_result()
            handled = True

        # Priority 3: CLI Fallback using ToolCallHandler
        if not handled:
            handler = ToolCallHandler()  # Use default handler with no policies
            result = await handler.handle(ui, call)

        current_results.approvals[call.tool_call_id] = result

        # Hook: PostToolUse / PostToolUseFailure
        from pydantic_ai import ToolApproved

        if isinstance(result, ToolApproved):
            await hook_manager.execute_hooks(
                HookEvent.POST_TOOL_USE,
                {"tool": call.tool_name, "args": call.args, "result": result},
            )
        elif isinstance(result, ToolDenied):
            await hook_manager.execute_hooks(
                HookEvent.POST_TOOL_USE_FAILURE,
                {"tool": call.tool_name, "args": call.args, "error": result.message},
            )

    return current_results
