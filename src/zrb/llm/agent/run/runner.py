"""LLM agent run loop: drives `pydantic_ai.Agent`, sanitizes history, retries.

Owns the `current_ui`, `current_tool_confirmation`, `current_yolo`, and
`current_approval_channel` `ContextVar`s — set on entry to `run_agent()`,
reset in `finally`. Every other module reads them through the wrappers in
`runtime_state.py` (re-exported from `zrb.contextvars`).

Sibling files in this package each own one concern:
  retry_loop.py       - decide-retry-or-not after a model exception
  history_utils.py    - sanitize_history(), strip_thinking_parts(), etc.
  error_classifier.py - is_invalid_tool_call_error / is_missing_reasoning_*
  openai_patch.py     - monkey-patch for `content: null` serialization
  deferred_calls.py   - resume after deferred tool requests

For the *why* behind history sanitization and the OpenAI patch, see
docs/advanced-topics/maintainer-guide.md#llm-history-sanitization-layer.
"""

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
from zrb.llm.agent.run.history_utils import sanitize_history
from zrb.llm.agent.run.hook_result_extractor import (
    extract_additional_context,
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
        ToolApproved,
        ToolCallPart,
        ToolDenied,
    )

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

_openai_patched = False


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
    global _openai_patched
    if not _openai_patched:
        patch_openai_model_response_serialization()
        _openai_patched = True

    (
        effective_ui,
        effective_tool_confirmation,
        effective_yolo,
        effective_approval_channel,
        effective_hook_manager,
    ) = _resolve_context_dependencies(
        ui, tool_confirmation, yolo, approval_channel, hook_manager
    )

    _log_startup(
        tool_confirmation,
        effective_tool_confirmation,
        approval_channel,
        effective_approval_channel,
    )

    token_ui = current_ui.set(effective_ui)
    token_confirmation = current_tool_confirmation.set(effective_tool_confirmation)
    token_yolo = current_yolo.set(effective_yolo)
    token_approval_channel = current_approval_channel.set(effective_approval_channel)

    try:
        effective_print_fn, effective_event_handler = _setup_print_and_events(
            print_fn, event_handler, effective_ui
        )

        effective_message = expand_prompt(message) if message else message

        effective_message, message_history = await _run_startup_hooks(
            message,
            message_history,
            attachments,
            effective_hook_manager,
            effective_message,
        )

        prompt_content = _get_prompt_content(effective_message, attachments, print_fn)
        prompt_content = await _apply_multimodal_fallback(
            prompt_content, agent, effective_print_fn
        )

        current_history = await _prepare_history(
            agent,
            message_history,
            prompt_content,
            limiter,
            system_prompt,
            print_fn,
            effective_hook_manager,
        )

        current_message = _merge_consecutive_messages(current_history, prompt_content)

        return await _execution_loop(
            agent=agent,
            current_message=current_message,
            current_history=current_history,
            print_fn=effective_print_fn,
            effective_event_handler=effective_event_handler,
            effective_tool_confirmation=effective_tool_confirmation,
            effective_ui=effective_ui,
            effective_hook_manager=effective_hook_manager,
            effective_approval_channel=effective_approval_channel,
        )
    finally:
        current_ui.reset(token_ui)
        current_tool_confirmation.reset(token_confirmation)
        current_yolo.reset(token_yolo)
        current_approval_channel.reset(token_approval_channel)


def _resolve_context_dependencies(
    ui, tool_confirmation, yolo, approval_channel, hook_manager
):
    # lazy: zrb.llm.ui.* and zrb.llm.approval.* are imported inside this
    # function to break a circular import — zrb.llm.agent is loaded by
    # those packages' init paths, so module-top imports here would re-enter
    # zrb.llm.agent before its __init__ has finished.
    # lazy: zrb internal (heavy via transitive / circular)
    from zrb.llm.ui.std_ui import StdUI

    ui_arg = ui if ui is not None else current_ui.get()
    if ui_arg is None:
        ui_arg = StdUI()

    if isinstance(ui_arg, list):
        if len(ui_arg) == 1:
            effective_ui = ui_arg[0]
        elif len(ui_arg) == 0:
            effective_ui = StdUI()
        else:
            # lazy: zrb internal (heavy via transitive / circular)
            from zrb.llm.ui.multi_ui import MultiUI

            effective_ui = MultiUI(ui_arg)
    else:
        effective_ui = ui_arg

    effective_tool_confirmation = tool_confirmation or current_tool_confirmation.get()
    effective_hook_manager = hook_manager or default_hook_manager
    effective_yolo = yolo or current_yolo.get()
    effective_approval_channel = approval_channel or current_approval_channel.get()

    if effective_approval_channel is not None and effective_ui is not None:
        # lazy: zrb internal (heavy via transitive / circular)
        from zrb.llm.approval.multiplex_approval_channel import (
            MultiplexApprovalChannel,
        )
        from zrb.llm.approval.terminal_approval_channel import TerminalApprovalChannel

        if not isinstance(effective_approval_channel, MultiplexApprovalChannel):
            ui_for_terminal = effective_ui
            if hasattr(effective_ui, "_uis") and effective_ui._uis:
                ui_for_terminal = effective_ui._uis[0]
            CFG.LOGGER.debug(
                f"Creating TerminalApprovalChannel with UI: {ui_for_terminal}"
            )
            terminal_channel = TerminalApprovalChannel(ui_for_terminal)
            effective_approval_channel = MultiplexApprovalChannel(
                [terminal_channel, effective_approval_channel]
            )
            CFG.LOGGER.debug("Wrapped approval channel: CLI first, then Telegram")

    return (
        effective_ui,
        effective_tool_confirmation,
        effective_yolo,
        effective_approval_channel,
        effective_hook_manager,
    )


def _log_startup(
    tool_confirmation,
    effective_tool_confirmation,
    approval_channel,
    effective_approval_channel,
):
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


def _setup_print_and_events(print_fn, event_handler, effective_ui):
    effective_print_fn = print_fn
    if effective_print_fn == print and effective_ui:
        effective_print_fn = effective_ui.append_to_output

    effective_event_handler = event_handler
    if effective_event_handler is None:
        # lazy: zrb.llm.util.stream_response transitively pulls pydantic_ai;
        # keeping this lazy preserves cold-start latency.
        from zrb.llm.util.stream_response import create_event_handler

        def _event_print_fn(text: str, kind: str) -> None:
            effective_ui.append_to_output(text, end="", kind=kind)

        effective_event_handler = create_event_handler(
            _event_print_fn,
            show_tool_call_detail=CFG.LLM_SHOW_TOOL_CALL_DETAIL,
            show_tool_result=CFG.LLM_SHOW_TOOL_CALL_RESULT,
        )
    return effective_print_fn, effective_event_handler


async def _run_startup_hooks(
    message, message_history, attachments, effective_hook_manager, effective_message
):
    session_start_results = await effective_hook_manager.execute_hooks(
        HookEvent.SESSION_START,
        {
            "message": message,
            "history": message_history,
            "attachments": attachments,
        },
    )

    session_start_context = extract_additional_context(session_start_results)
    if session_start_context:
        CFG.LOGGER.debug(
            f"SESSION_START hook provided additionalContext: {session_start_context[:100]}..."
        )
        # lazy: heavy third-party
        from pydantic_ai.messages import ModelRequest, SystemPromptPart

        context_part = SystemPromptPart(content=session_start_context)
        if message_history and isinstance(message_history[0], ModelRequest):
            message_history[0].parts.insert(0, context_part)
        else:
            message_history = [ModelRequest(parts=[context_part])] + message_history

    user_prompt_results = await effective_hook_manager.execute_hooks(
        HookEvent.USER_PROMPT_SUBMIT,
        {
            "original_message": message,
            "expanded_message": effective_message,
            "attachments": attachments,
        },
    )

    prompt_context = extract_additional_context(user_prompt_results)
    if prompt_context:
        CFG.LOGGER.debug(
            f"USER_PROMPT_SUBMIT hook provided additionalContext: {prompt_context[:100]}..."
        )
        if effective_message:
            effective_message = f"{prompt_context}\n\n{effective_message}"
        else:
            effective_message = prompt_context

    return effective_message, message_history


async def _prepare_history(
    agent,
    message_history,
    prompt_content,
    limiter,
    system_prompt,
    print_fn,
    effective_hook_manager,
):
    history_processors = list(getattr(agent, "_zrb_history_processors", None) or [])

    # Count system prompt tokens BEFORE running processors so the summarizer
    # can account for them in its threshold comparison (the "Total" shown in
    # the usage indicator includes system prompt, not just message history).
    reserved_tokens = limiter.count_tokens(system_prompt) if system_prompt else 0
    CFG.LOGGER.debug(f"System prompt reserved tokens: {reserved_tokens}")

    # Count tokens once here so we can pass it to the hook without an extra O(n) call.
    pre_process_tokens = limiter.count_tokens(message_history)

    await effective_hook_manager.execute_hooks(
        HookEvent.PRE_COMPACT,
        {
            "history": message_history,
            "token_count": pre_process_tokens,
            "message_count": len(message_history),
            "has_history_processors": bool(history_processors),
        },
    )

    processed_history = message_history
    for processor in history_processors:
        processed_history = await processor(processed_history, reserved_tokens)

    processed_history = ensure_alternating_roles(processed_history)

    effective_limit = max(0, limiter.max_token_per_request - reserved_tokens)
    # Reuse the token count from the hook when no processors ran — they are the only
    # thing that can materially change the history content between the two points.
    # ensure_alternating_roles only merges consecutive same-role messages, which is a
    # no-op on well-formed history, so the slight approximation is safe.
    current_tokens = (
        limiter.count_tokens(processed_history)
        if history_processors
        else pre_process_tokens
    )
    if current_tokens > effective_limit:
        print_fn(
            f"\n[SYSTEM] History too large ({current_tokens} tokens) after summarization. Force pruning..."
        )
        safe_history = []
        if (
            processed_history
            and limiter.count_tokens(processed_history[-1]) < effective_limit
        ):
            safe_history = [processed_history[-1]]
        processed_history = safe_history

    return await _acquire_rate_limit(
        limiter, prompt_content, processed_history, print_fn, reserved_tokens
    )


def _merge_consecutive_messages(current_history, current_message):
    # lazy: heavy third-party
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    if (
        current_history
        and isinstance(current_history[-1], ModelRequest)
        and current_message is not None
    ):
        if isinstance(current_message, str):
            current_history[-1].parts.append(UserPromptPart(content=current_message))
        elif isinstance(current_message, list):
            current_history[-1].parts.append(UserPromptPart(content=current_message))
        return None
    return current_message


async def _apply_history_processors(
    history: list[Any], processors: list[Any]
) -> list[Any]:
    """Apply history processors and ensure proper message alternation.

    Called between tool-call iterations so that summarization effects (e.g.
    replacing a large tool result with a SUMMARY_PREFIX string) are written
    back to current_history. Without this, pydantic-ai's before_model_request
    modifies a shallow copy and result.all_messages() always returns the
    original unsummarized content, causing large tool results to be
    re-summarized on every subsequent model call.
    """
    processed = history
    for processor in processors:
        try:
            processed = await processor(processed)
        except Exception as e:
            CFG.LOGGER.warning(f"History processor failed between tool calls: {e}")
    return ensure_alternating_roles(processed)


async def _execution_loop(
    agent: "Agent[None, Any]",
    current_message: Any,
    current_history: list[Any],
    print_fn: Callable[[str], Any],
    effective_event_handler: Callable[[Any], Any] | None,
    effective_tool_confirmation: AnyToolConfirmation,
    effective_ui: UIProtocol | None,
    effective_hook_manager: HookManager,
    effective_approval_channel: "ApprovalChannel | None",
) -> tuple[Any, list[Any]]:
    # lazy: heavy third-party
    from pydantic_ai import AgentRunResultEvent, DeferredToolRequests, UsageLimits

    run_history = current_history
    result_output = None
    retry_state = RetryState()
    extension_state = ExtensionState()
    current_results = None
    # pydantic-ai's before_model_request runs history processors on a shallow
    # copy of ctx.state.message_history, so any summarization it does is never
    # written back. result.all_messages() therefore always returns the original
    # (unsummarized) content. We hold a reference to the processors here so we
    # can apply them ourselves to persist their effects between tool call
    # iterations.
    history_processors = list(getattr(agent, "_zrb_history_processors", None) or [])

    try:
        while True:
            current_history = sanitize_history(
                current_history,
                allow_orphaned_tool_calls=(current_results is not None),
            )
            stream_error = None
            try:
                # Docs: https://pydantic.dev/docs/ai/core-concepts/agent/#streaming-events-and-final-output
                async with agent.run_stream_events(
                    current_message,
                    message_history=current_history,
                    deferred_tool_results=current_results,
                    usage_limits=UsageLimits(request_limit=None),
                ) as stream:
                    CFG.LOGGER.debug(
                        f"Stream started, current_results={current_results}"
                    )
                    async for event in stream:
                        if isinstance(event, AgentRunResultEvent):
                            result = event.result
                            result_output = result.output
                            CFG.LOGGER.debug(
                                f"Got result event, result_output type: {type(result_output)}"
                            )
                            run_history = sanitize_history(
                                result.all_messages(),
                                allow_orphaned_tool_calls=isinstance(
                                    result_output, DeferredToolRequests
                                ),
                            )
                        if effective_event_handler:
                            await effective_event_handler(event)
            except Exception as _stream_exc:
                stream_error = _stream_exc

            if stream_error is not None:
                outcome = await handle_stream_error(
                    retry_state,
                    stream_error,
                    current_history,
                    current_message,
                    run_history,
                    print_fn,
                    min_turns=1 if current_results is not None else 0,
                )
                if not outcome.should_retry:
                    raise stream_error
                current_history = outcome.new_history
                current_message = outcome.new_message
                continue

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
                    await effective_hook_manager.execute_hooks(
                        HookEvent.SESSION_END,
                        {"reason": "deferred_wait", "history": run_history},
                    )
                    return result_output, run_history

                current_results = rebuild_for_denials(current_results)
                current_message = None
                current_history = await _apply_history_processors(
                    run_history, history_processors
                )
                CFG.LOGGER.debug("Continuing to next iteration with current_results")
                continue

            session_end_results = await effective_hook_manager.execute_hooks(
                HookEvent.SESSION_END,
                {"output": result_output, "history": run_history},
            )

            ext_outcome = apply_session_end_extension(
                session_end_results,
                extension_state,
                result_output,
                run_history,
                print_fn,
            )
            if ext_outcome.should_continue:
                current_message = ext_outcome.new_message
                current_history = ext_outcome.new_history
                result_output = None
                current_results = None
                continue

            return resolve_extended_return(extension_state, result_output, run_history)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        if not hasattr(e, "zrb_history"):
            setattr(e, "zrb_history", run_history)
        raise e


async def _acquire_rate_limit(
    limiter: LLMLimiter,
    message: str | None,
    message_history: list[Any],
    print_fn: Callable[..., Any],
    reserved_tokens: int = 0,
) -> list[Any]:
    """Prunes history and waits if rate limits are exceeded."""

    def notify_throttling(msg: str):
        if not msg:
            try:
                print_fn("\r\033[K", end="")
            except TypeError:
                pass
            return
        try:
            print_fn(f"\r{msg}", end="")
        except TypeError:
            print_fn(msg)

    if not message:
        return message_history
    pruned_history = limiter.fit_context_window(
        message_history, message, reserved_tokens
    )
    await limiter.acquire(
        {"message": message, "history": pruned_history},
        notifier=notify_throttling,
    )
    return pruned_history


async def _apply_multimodal_fallback(
    prompt_content: Any,
    agent: "Agent[None, Any]",
    print_fn: Callable[..., Any],
) -> Any:
    """Replace binaries the main model can't consume with text descriptions.

    No-op when *prompt_content* is a string or has no binaries. When the
    main model is text-only and a multimodal model is configured, image and
    audio attachments are routed through a one-shot describe sub-agent and
    their textual output is inlined; unsupported attachments are dropped
    with a warning rather than silently sent to a provider that will reject
    or ignore them.
    """
    # lazy: util.multimodal_describe imports the agent stack; keeping it
    # local avoids re-entering zrb.llm.agent during its own __init__ chain.
    from zrb.llm.config.config import llm_config

    # lazy: zrb internal (heavy via transitive / circular)
    from zrb.llm.util.multimodal_describe import replace_unsupported_attachments

    main_model = getattr(agent, "model", None)
    return await replace_unsupported_attachments(
        prompt_content,
        main_model=main_model,
        multimodal_model=llm_config.multimodal_model,
        print_fn=print_fn,
    )
