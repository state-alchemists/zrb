from __future__ import annotations

import asyncio
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Awaitable, Callable, TypeAlias

from zrb.config.config import CFG
from zrb.llm.agent.run.deferred_calls import (
    process_deferred_requests as _process_deferred_requests,
)
from zrb.llm.agent.run.deferred_calls import (
    rebuild_for_denials,
)
from zrb.llm.agent.run.history_utils import filter_nil_content
from zrb.llm.agent.run.hook_result_extractor import (
    extract_additional_context,
    extract_replace_response,
    extract_system_message,
)
from zrb.llm.agent.run.openai_patch import patch_openai_model_response_serialization
from zrb.llm.agent.run.prompt_content import get_prompt_content as _get_prompt_content
from zrb.llm.agent.run.retry_loop import RetryState, handle_stream_error
from zrb.llm.agent.run.session_extension import (
    ExtensionState,
    apply_session_end_extension,
    resolve_extended_return,
)
from zrb.llm.approval.approval_channel import ApprovalChannel, current_approval_channel
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.manager import hook_manager as default_hook_manager
from zrb.llm.hook.types import HookEvent
from zrb.llm.message import ensure_alternating_roles
from zrb.llm.tool_call.handler import ToolCallHandler
from zrb.llm.tool_call.ui_protocol import UIProtocol
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

    AnyToolConfirmation: TypeAlias = (
        Callable[
            [ToolCallPart],
            ToolApproved | ToolDenied | Awaitable[ToolApproved | ToolDenied],
        ]
        | ToolCallHandler
        | None
    )
else:
    AnyToolConfirmation: TypeAlias = Any


current_ui: ContextVar[UIProtocol | None] = ContextVar("current_ui", default=None)


current_tool_confirmation: ContextVar[AnyToolConfirmation] = ContextVar(
    "current_tool_confirmation", default=None
)
current_yolo: ContextVar[bool] = ContextVar("current_yolo", default=False)
patch_openai_model_response_serialization()


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
        session_start_context = extract_additional_context(session_start_results)
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
        prompt_context = extract_additional_context(user_prompt_results)
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
        history_processors = list(getattr(agent, "history_processors", None) or [])

        # Hook: PreCompact - invoked before history processing/summarization
        await effective_hook_manager.execute_hooks(
            HookEvent.PRE_COMPACT,
            {
                "history": message_history,
                "token_count": limiter.count_tokens(message_history),
                "message_count": len(message_history),
                "has_history_processors": bool(history_processors),
            },
        )

        # Run processors once here (before pruning) so summarization runs
        # on raw history and compresses before fit_context_window would hard-cut.
        # pydantic-ai re-runs them per-request inside run_stream_events —
        # that's fine: idempotent summarizers early-return when under threshold,
        # and PII/sanitization processors must run on every outbound request.
        processed_history = message_history
        for processor in history_processors:
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
                f"\n[SYSTEM] History too large ({current_tokens} tokens) after summarization. Force pruning..."
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
        retry_state = RetryState()
        extension_state = ExtensionState()
        try:
            while True:
                # Filter out nil content before sending to API
                current_history = filter_nil_content(current_history)
                # request_limit=None overrides pydantic-ai's default of 50,
                # which would otherwise cut off long tool-use loops.
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
                            run_history = filter_nil_content(result.all_messages())
                        if effective_event_handler:
                            await effective_event_handler(event)
                except Exception as _stream_exc:
                    stream_error = _stream_exc
                finally:
                    if stream is not None and hasattr(stream, "aclose"):
                        await stream.aclose()

                if stream_error is not None:
                    outcome = await handle_stream_error(
                        retry_state,
                        stream_error,
                        current_history,
                        current_message,
                        run_history,
                        print_fn,
                    )
                    if not outcome.should_retry:
                        raise stream_error
                    current_history = outcome.new_history
                    current_message = outcome.new_message
                    continue

                # Handle Deferred Calls
                if isinstance(result_output, DeferredToolRequests):
                    CFG.LOGGER.debug(
                        "Got DeferredToolRequests, calling process_deferred_requests"
                    )
                    current_results = await _process_deferred_requests(
                        result_output,
                        effective_tool_confirmation,
                        effective_ui,
                        effective_hook_manager,
                        effective_approval_channel,
                    )
                    CFG.LOGGER.debug(
                        f"process_deferred_requests returned: {current_results}"
                    )
                    if current_results is None:
                        # Hook: SessionEnd (premature end due to tool denial or wait)
                        await effective_hook_manager.execute_hooks(
                            HookEvent.SESSION_END,
                            {"reason": "deferred_wait", "history": run_history},
                        )
                        return result_output, run_history

                    current_results = rebuild_for_denials(current_results)

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

                ext_outcome = apply_session_end_extension(
                    session_end_results,
                    extension_state,
                    result_output,
                    run_history,
                    effective_print_fn,
                )
                if ext_outcome.should_continue:
                    current_message = ext_outcome.new_message
                    current_history = ext_outcome.new_history
                    result_output = None
                    current_results = None
                    continue

                return resolve_extended_return(
                    extension_state, result_output, run_history
                )
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
