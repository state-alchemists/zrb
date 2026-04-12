from __future__ import annotations

import asyncio
import json
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Awaitable, Callable, TypeAlias, Union

from zrb.config.config import CFG
from zrb.llm.approval.approval_channel import ApprovalChannel, current_approval_channel
from zrb.llm.config.limiter import LLMLimiter, is_turn_start
from zrb.llm.hook.executor import HookExecutionResult
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


def _is_prompt_too_long_error(e: Exception) -> bool:
    """Returns True if the exception is a context length / token limit error."""
    err_str = str(e).lower()
    context_keywords = [
        "prompt too long",
        "context length",
        "context window",
        "max tokens",
        "token limit",
        "input too long",
        "maximum context",
    ]
    return any(keyword in err_str for keyword in context_keywords)


def _drop_oldest_turn(history: list[Any]) -> list[Any]:
    """Removes the oldest conversation turn from history."""
    if not history:
        return history
    # Find the start of the second turn and drop everything before it
    for i in range(1, len(history)):
        if is_turn_start(history[i]):
            return history[i:]
    # Only one turn (or no clear boundary) — clear all
    return []


def _filter_nil_content(messages: list[Any]) -> list[Any]:
    """Filter out parts with None/nil content from messages.

    This prevents "invalid message content type: <nil>" errors from OpenAI-compatible APIs.
    Must be called at runtime before passing messages to the model.
    """
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        ToolCallPart,
        ToolReturnPart,
    )

    filtered = []
    for msg in messages:
        if isinstance(msg, ModelRequest):
            # Filter parts in ModelRequest
            valid_parts = []
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    # Keep tool calls that have a tool_name
                    if part.tool_name:
                        valid_parts.append(part)
                elif isinstance(part, ToolReturnPart):
                    # Keep tool returns, ensure content is not None
                    if part.content is not None:
                        valid_parts.append(part)
                elif hasattr(part, "content"):
                    # TextPart, UserPromptPart, etc. - keep if content is not None
                    if part.content is not None:
                        valid_parts.append(part)
                else:
                    # Parts without content field - keep as-is
                    valid_parts.append(part)
            if valid_parts:
                from dataclasses import replace

                filtered.append(replace(msg, parts=valid_parts))
        elif isinstance(msg, ModelResponse):
            # Filter parts in ModelResponse
            valid_parts = []
            for part in msg.parts:
                if hasattr(part, "content"):
                    if part.content is not None:
                        valid_parts.append(part)
                else:
                    valid_parts.append(part)
            if valid_parts:
                from dataclasses import replace

                filtered.append(replace(msg, parts=valid_parts))
        else:
            # Unknown message type - keep as-is
            filtered.append(msg)
    return filtered


def _extract_system_message(hook_results: list[HookExecutionResult]) -> str | None:
    """Extract the first systemMessage from hook results, if any.

    Claude Code hooks can return systemMessage to inject context into the conversation.
    This helper extracts it from hook results for processing.

    Args:
        hook_results: List of hook execution results

    Returns:
        The first systemMessage found, or None if no hooks returned a message.
    """
    for result in hook_results:
        if result.system_message:
            return result.system_message
    return None


def _extract_replace_response(hook_results: list[HookExecutionResult]) -> bool:
    """Extract the replaceResponse flag from hook results.

    If any hook returns replaceResponse=True, the extended session's response
    should replace the original response. Default is False (return original).

    Args:
        hook_results: List of hook execution results

    Returns:
        True if any hook wants to replace the response, False otherwise.
    """
    for result in hook_results:
        if result.replace_response:
            return True
    return False


def _extract_additional_context(hook_results: list[HookExecutionResult]) -> str | None:
    """Extract the first additionalContext from hook results, if any.

    Claude Code hooks can return additionalContext to prepend context to the conversation.
    This helper extracts it from hook results for processing.

    Args:
        hook_results: List of hook execution results

    Returns:
        The first additionalContext found, or None if no hooks returned context.
    """
    for result in hook_results:
        if result.additional_context:
            return result.additional_context
    return None


current_tool_confirmation: ContextVar[AnyToolConfirmation] = ContextVar(
    "current_tool_confirmation", default=None
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
    ui: UIProtocol | list[UIProtocol] | None = None,
    hook_manager: HookManager | None = None,
    yolo: bool = False,
    approval_channel: "ApprovalChannel | None" = None,
    system_prompt: str = "",
) -> tuple[Any, list[Any]]:
    """
    Runs the agent with rate limiting, history management, and optional CLI confirmation loop.
    Returns (result_output, new_message_history).
    """
    from pydantic_ai import AgentRunResultEvent, DeferredToolRequests, UsageLimits

    from zrb.llm.ui.std_ui import StdUI

    # Resolve UI - handle both single UI and list of UIs
    ui_arg = ui
    if ui_arg is None:
        ui_arg = current_ui.get()
    if ui_arg is None:
        ui_arg = StdUI()
    # Create MultiUI if multiple UIs
    if isinstance(ui_arg, list):
        if len(ui_arg) == 1:
            effective_ui = ui_arg[0]
        elif len(ui_arg) == 0:
            effective_ui = StdUI()
        else:
            from zrb.llm.ui.multi_ui import MultiUI

            effective_ui = MultiUI(ui_arg)
    else:
        effective_ui = ui_arg

    effective_tool_confirmation = tool_confirmation or current_tool_confirmation.get()
    effective_hook_manager = hook_manager or default_hook_manager
    effective_yolo = yolo or current_yolo.get()
    effective_approval_channel = approval_channel or current_approval_channel.get()

    # If approval_channel exists but doesn't have UI for terminal, add it
    if effective_approval_channel is not None and effective_ui is not None:
        from zrb.llm.approval.multiplex_approval_channel import MultiplexApprovalChannel
        from zrb.llm.approval.terminal_approval_channel import TerminalApprovalChannel

        # Check if we need to add terminal approval channel
        if not isinstance(effective_approval_channel, MultiplexApprovalChannel):
            # Get the first UI for terminal approval (not MultiUI)
            ui_for_terminal = effective_ui
            if hasattr(effective_ui, "_uis") and effective_ui._uis:
                ui_for_terminal = effective_ui._uis[0]
            CFG.LOGGER.debug(
                f"Creating TerminalApprovalChannel with UI: {ui_for_terminal}"
            )
            terminal_channel = TerminalApprovalChannel(ui_for_terminal)
            # CLI first, then Telegram - CLI gets priority
            effective_approval_channel = MultiplexApprovalChannel(
                [
                    terminal_channel,
                    effective_approval_channel,
                ]
            )
            CFG.LOGGER.debug("Wrapped approval channel: CLI first, then Telegram")

    CFG.LOGGER.debug("run_agent === START ===")
    CFG.LOGGER.debug(f"tool_confirmation param: {tool_confirmation}")
    CFG.LOGGER.debug(
        f"current_tool_confirmation.get(): {current_tool_confirmation.get()}"
    )
    CFG.LOGGER.debug(f"effective_tool_confirmation: {effective_tool_confirmation}")
    CFG.LOGGER.debug(f"approval_channel param: {approval_channel}")
    CFG.LOGGER.debug(
        f"current_approval_channel.get(): {current_approval_channel.get()}"
    )
    CFG.LOGGER.debug(f"effective_approval_channel: {effective_approval_channel}")

    # Set context variables so sub-agents can inherit them
    token_ui = current_ui.set(effective_ui)
    token_confirmation = current_tool_confirmation.set(effective_tool_confirmation)
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
            from zrb.llm.util.stream_response import create_event_handler

            def _event_print_fn(text: str, kind: str) -> None:
                effective_ui.append_to_output(text, end="", kind=kind)

            effective_event_handler = create_event_handler(
                _event_print_fn,
                show_tool_call_detail=CFG.LLM_SHOW_TOOL_CALL_DETAIL,
                show_tool_result=CFG.LLM_SHOW_TOOL_CALL_RESULT,
            )

        # Hook: SessionStart - hooks can inject additionalContext into conversation
        session_start_results = await effective_hook_manager.execute_hooks(
            HookEvent.SESSION_START,
            {
                "message": message,
                "history": message_history,
                "attachments": attachments,
            },
        )

        # Process additionalContext from SESSION_START hooks
        # This allows hooks to inject context before the conversation starts
        session_start_context = _extract_additional_context(session_start_results)
        if session_start_context:
            CFG.LOGGER.debug(
                f"SESSION_START hook provided additionalContext: {session_start_context[:100]}..."
            )
            # additionalContext is prepended to the conversation as a system message
            # This is done by adding it to message_history with a SystemPromptPart-like approach
            from pydantic_ai.messages import ModelRequest, SystemPromptPart

            context_part = SystemPromptPart(content=session_start_context)
            # Prepend to history
            if message_history and isinstance(message_history[0], ModelRequest):
                # Add to existing first request
                message_history[0].parts.insert(0, context_part)
            else:
                # Create new request with context
                message_history = [ModelRequest(parts=[context_part])] + message_history

        # Expand user message with references
        effective_message = expand_prompt(message) if message else message

        # Hook: UserPromptSubmit - hooks can modify prompt or inject additionalContext
        user_prompt_results = await effective_hook_manager.execute_hooks(
            HookEvent.USER_PROMPT_SUBMIT,
            {
                "original_message": message,
                "expanded_message": effective_message,
                "attachments": attachments,
            },
        )

        # Process additionalContext from USER_PROMPT_SUBMIT hooks
        # This allows hooks to prepend context to the user's prompt
        prompt_context = _extract_additional_context(user_prompt_results)
        if prompt_context:
            CFG.LOGGER.debug(
                f"USER_PROMPT_SUBMIT hook provided additionalContext: {prompt_context[:100]}..."
            )
            # Prepend context to the effective message
            if effective_message:
                effective_message = f"{prompt_context}\n\n{effective_message}"
            else:
                effective_message = prompt_context

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

        # Count reserved tokens for system prompt (not included in history)
        reserved_tokens = limiter.count_tokens(system_prompt) if system_prompt else 0
        CFG.LOGGER.debug(f"System prompt reserved tokens: {reserved_tokens}")

        # EMERGENCY FAILSAFE: If summarization failed to reduce size below limit
        # (e.g. resulted in a 1M token summary), we must hard-prune to avoid API crash.
        effective_limit = max(0, limiter.max_token_per_request - reserved_tokens)
        current_tokens = limiter.count_tokens(processed_history)
        if current_tokens > effective_limit:
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
                and limiter.count_tokens(processed_history[-1]) < effective_limit
            ):
                safe_history = [processed_history[-1]]
            processed_history = safe_history

        current_history = await _acquire_rate_limit(
            limiter, prompt_content, processed_history, print_fn, reserved_tokens
        )
        current_message = prompt_content
        current_results = None

        # 2. Safety Check: Merge consecutive ModelRequest if needed
        # (e.g. if history was summarized and ends with a ModelRequest)
        from pydantic_ai.messages import ModelRequest, UserPromptPart

        if (
            current_history
            and isinstance(current_history[-1], ModelRequest)
            and current_message is not None
        ):
            # current_message can be: str, list[UserContent], or None
            if isinstance(current_message, str):
                current_history[-1].parts.append(
                    UserPromptPart(content=current_message)
                )
            elif isinstance(current_message, list):
                # Multimodal: wrap the content list in a single UserPromptPart
                current_history[-1].parts.append(
                    UserPromptPart(content=current_message)
                )
            # Set to None so pydantic_ai doesn't add another request
            current_message = None

        # 3. Execution Loop
        run_history = current_history
        result_output = None
        stream = None
        _context_retry_count = 0
        _MAX_CONTEXT_RETRIES = CFG.LLM_MAX_CONTEXT_RETRIES
        try:
            while True:
                # Filter out nil content before sending to API
                current_history = _filter_nil_content(current_history)
                stream = agent.run_stream_events(
                    current_message,
                    message_history=current_history,
                    deferred_tool_results=current_results,
                    usage_limits=UsageLimits(request_limit=None),
                )
                CFG.LOGGER.debug(f"Stream started, current_results={current_results}")
                stream_error = None
                try:
                    async for event in stream:
                        await asyncio.sleep(0)
                        if isinstance(event, AgentRunResultEvent):
                            result = event.result
                            result_output = result.output
                            CFG.LOGGER.debug(
                                f"Got result event, result_output type: {type(result_output)}"
                            )
                            run_history = _filter_nil_content(result.all_messages())
                        if effective_event_handler:
                            await effective_event_handler(event)
                except Exception as _stream_exc:
                    stream_error = _stream_exc
                finally:
                    # Ensure stream is closed on cancellation or completion
                    if stream is not None and hasattr(stream, "aclose"):
                        await stream.aclose()

                if stream_error is not None:
                    if (
                        _is_prompt_too_long_error(stream_error)
                        and _context_retry_count < _MAX_CONTEXT_RETRIES
                    ):
                        _context_retry_count += 1
                        # Drop one conversation turn from history and retry
                        current_history = _drop_oldest_turn(current_history)
                        print_fn(
                            f"\n[System] Context too long, retrying with reduced history"
                            f" (attempt {_context_retry_count}/{_MAX_CONTEXT_RETRIES})..."
                        )
                        CFG.LOGGER.debug(
                            f"Prompt too long: retrying with {len(current_history)} history messages"
                        )
                        continue
                    raise stream_error

                # Handle Deferred Calls
                if isinstance(result_output, DeferredToolRequests):
                    CFG.LOGGER.debug(
                        "Got DeferredToolRequests, calling _process_deferred_requests"
                    )
                    current_results = await _process_deferred_requests(
                        result_output,
                        effective_tool_confirmation,
                        effective_ui,
                        effective_hook_manager,
                        effective_approval_channel,
                    )
                    CFG.LOGGER.debug(
                        f"_process_deferred_requests returned: {current_results}"
                    )
                    if current_results is None:
                        # Hook: SessionEnd (premature end due to tool denial or wait)
                        await effective_hook_manager.execute_hooks(
                            HookEvent.SESSION_END,
                            {"reason": "deferred_wait", "history": run_history},
                        )
                        return result_output, run_history

                    # If any tool was denied, we need to create a NEW DeferredToolResults
                    # with empty calls (so pydantic AI doesn't execute them)
                    from pydantic_ai import DeferredToolResults
                    from pydantic_ai.tools import ToolDenied

                    has_denials = any(
                        isinstance(v, ToolDenied)
                        for v in current_results.approvals.values()
                    )

                    if has_denials:
                        # Create new results with empty calls but preserve approvals
                        current_results = DeferredToolResults(
                            calls={},  # Empty calls = don't execute any tools
                            approvals=current_results.approvals,
                            metadata=current_results.metadata,
                        )
                        CFG.LOGGER.debug(
                            "Tool was denied, clearing calls in deferred results"
                        )

                    # Prepare next iteration
                    current_message = None
                    current_history = run_history
                    CFG.LOGGER.debug(
                        "Continuing to next iteration with current_results"
                    )
                    continue

                # Hook: SessionEnd - check if hooks want to extend session
                session_end_results = await effective_hook_manager.execute_hooks(
                    HookEvent.SESSION_END,
                    {"output": result_output, "history": run_history},
                )

                # Check if any hook wants to extend the session with a systemMessage
                # This allows hooks (like journaling) to trigger LLM actions at session end
                session_end_message = _extract_system_message(session_end_results)
                replace_response = _extract_replace_response(session_end_results)

                if session_end_message:
                    CFG.LOGGER.debug(
                        f"SESSION_END hook returned systemMessage, continuing session: {session_end_message[:100]}..."
                    )
                    CFG.LOGGER.debug(
                        f"SESSION_END hook replace_response={replace_response}"
                    )
                    # Capture original BEFORE extending session (critical for restore)
                    _original_output = result_output
                    _original_history = run_history
                    # Convert systemMessage to user prompt for next iteration
                    effective_print_fn(f"\n[System] {session_end_message}\n")
                    # Continue the session with the system message as user prompt
                    current_message = session_end_message
                    current_history = run_history
                    # Reset state for next iteration
                    result_output = None
                    current_results = None
                    # Track whether to return extended or original response
                    # If multiple extensions, last one wins
                    _return_extended = replace_response
                    continue

                # Return appropriate result based on replace_response flag
                # If replace_response=True, return extended response (from last iteration)
                # If replace_response=False (default), return original response saved before extension
                if "_return_extended" in locals():
                    if _return_extended:
                        # Extended session response replaces original
                        CFG.LOGGER.debug(
                            "Returning extended response (replace_response=True)"
                        )
                        return result_output, run_history
                    else:
                        # Default: return original response (extended was for side effects)
                        CFG.LOGGER.debug(
                            "Returning original response (replace_response=False)"
                        )
                        return _original_output, _original_history
                else:
                    # No session extension occurred, return current result
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
        current_yolo.reset(token_yolo)
        current_approval_channel.reset(token_approval_channel)


def _get_prompt_content(
    message: str | None, attachments: list[Any] | None, print_fn: Callable[[str], Any]
) -> "list[Any] | str | None":
    """Build prompt content for pydantic-ai agent.

    Returns:
        - str: text-only prompt (passed directly to run_stream_events)
        - list[UserContent]: multimodal prompt (text + attachments, passed directly)
        - None: empty prompt

    run_stream_events expects str | Sequence[UserContent], NOT a UserPromptPart wrapper.
    The merge-into-history path below wraps the list in UserPromptPart as needed.
    """
    if not attachments:
        return message

    attachments = normalize_attachments(attachments, print_fn)
    if not attachments:
        return message if message else None

    # Return content as a flat list: [text?, *attachments]
    # pydantic-ai accepts list[UserContent] directly as the user_prompt argument.
    if message:
        content: list[Any] = [message]
        content.extend(attachments)
        return content
    else:
        return list(attachments)


async def _acquire_rate_limit(
    limiter: LLMLimiter,
    message: str | None,
    message_history: list[Any],
    print_fn: Callable[..., Any],
    reserved_tokens: int = 0,
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
    # Prune history, accounting for reserved tokens (e.g. system prompt, tool schemas)
    pruned_history = limiter.fit_context_window(
        message_history, message, reserved_tokens
    )
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

        # Priority 1: Tool Policy (automatic approval based on rules)
        if effective_tool_confirmation:
            if isinstance(effective_tool_confirmation, ToolCallHandler):
                policy_result = await effective_tool_confirmation.check_policies(
                    ui, call
                )
                if policy_result is not None:
                    result = policy_result
                    handled = True

        # Priority 2: Approval channel handles multi-channel approval
        # (MultiplexApprovalChannel races all channels concurrently - first response wins)
        if not handled and approval_channel is not None:
            CFG.LOGGER.debug(f"Using approval channel for {call.tool_name}")

            # Prepare args for approval channel
            args = {}
            if hasattr(call, "args") and call.args:
                if isinstance(call.args, dict):
                    args = call.args
                elif isinstance(call.args, str):
                    try:
                        args = json.loads(call.args)
                    except json.JSONDecodeError:
                        pass

            context = ApprovalContext(
                tool_name=call.tool_name,
                tool_args=args,
                tool_call_id=call.tool_call_id,
            )
            CFG.LOGGER.debug("Calling approval_channel.request_approval()...")
            approval_result = await approval_channel.request_approval(context)
            CFG.LOGGER.debug(
                f"Approval channel returned: approved={approval_result.approved}"
            )
            result = approval_result.to_pydantic_result()
            handled = True

        # Priority 3: CLI fallback (no approval channel, but have tool confirmation)
        if not handled:
            CFG.LOGGER.debug(f"Using CLI fallback for {call.tool_name}")
            if isinstance(effective_tool_confirmation, ToolCallHandler):
                result = await effective_tool_confirmation.handle(ui, call)
                CFG.LOGGER.debug(f"CLI handler returned: {result}")
            elif callable(effective_tool_confirmation):
                res = effective_tool_confirmation(call)
                if inspect.isawaitable(res):
                    result = await res
                else:
                    result = res
                CFG.LOGGER.debug(f"CLI callable returned: {result}")
            handled = True

        current_results.approvals[call.tool_call_id] = result

        # If denied, also remove from calls to prevent execution
        from pydantic_ai import ToolDenied

        if isinstance(result, ToolDenied):
            # Remove this call from the results so pydantic AI doesn't execute it
            if (
                hasattr(current_results, "calls")
                and call.tool_call_id in current_results.calls
            ):
                del current_results.calls[call.tool_call_id]
            CFG.LOGGER.debug("Tool denied, removed from calls")

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
