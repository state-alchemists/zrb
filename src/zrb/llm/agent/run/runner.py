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
from contextlib import ExitStack
from contextvars import ContextVar
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Awaitable, Callable, TypeAlias

from zrb.config.config import CFG
from zrb.llm.agent.run.deferred_calls import (
    process_deferred_requests as _process_deferred_requests,
)
from zrb.llm.agent.run.deferred_calls import (
    rebuild_for_denials,
)
from zrb.llm.agent.run.error_classifier import classify_error_type
from zrb.llm.agent.run.history_utils import (
    _append_live_context,
    _history_without_trailing_response,
    _is_empty_completion,
    _merge_consecutive_messages,
    sanitize_history,
)
from zrb.llm.agent.run.hook_result_extractor import (
    extract_additional_context,
    extract_block_decision,
    extract_continue_decision,
)
from zrb.llm.agent.run.openai_patch import patch_openai_model_response_serialization
from zrb.llm.agent.run.partial_run import PartialRunAccumulator
from zrb.llm.agent.run.prompt_content import get_prompt_content as _get_prompt_content
from zrb.llm.agent.run.retry_loop import RetryState, handle_stream_error
from zrb.llm.agent.run.session_extension import (
    ExtensionState,
    apply_turn_end_extension,
    resolve_extended_return,
)
from zrb.llm.agent.run.setup import (
    _bind_contextvar,
    _log_startup,
    _resolve_context_dependencies,
    _setup_print_and_events,
)
from zrb.llm.approval.approval_channel import ApprovalChannel, current_approval_channel
from zrb.llm.config.config import llm_config
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.types import HookEvent
from zrb.llm.message import ensure_alternating_roles
from zrb.llm.permission.state import (
    current_permission_policy,
    enter_agent_mode_scope,
    exit_agent_mode_scope,
)
from zrb.llm.sandbox.state import current_sandbox_policy
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
# The hook manager active for the current run. Read by nested tools (e.g. the
# delegate tool fires SubagentStart/Stop on the parent run's manager).
current_hook_manager: ContextVar[HookManager | None] = ContextVar(
    "current_hook_manager", default=None
)

# Process-wide guard: the OpenAI serialization patch is global and idempotent,
# so it only needs to run once per process. The check-then-set is safe under
# CPython's GIL for this single-process, asyncio (single-thread) usage; re-running
# the patch would be harmless anyway.
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
    yolo: bool | None = False,
    approval_channel: "ApprovalChannel | None" = None,
    system_prompt: str = "",
    live_context: str = "",
    permission_policy: Any = None,
    sandbox_policy: Any = None,
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

    # Set the policy from the explicit arg, else keep whatever a parent run set
    # (sub-agent inheritance), else None (legacy: nothing constrained).
    effective_policy = (
        permission_policy
        if permission_policy is not None
        else current_permission_policy.get()
    )
    # Same inheritance rule for the sandbox: explicit arg wins, else keep the
    # parent run's policy (sub-agents), else None (resolved from CFG at the
    # gate / shell tool — off unless the deployment opted in).
    effective_sandbox = (
        sandbox_policy if sandbox_policy is not None else current_sandbox_policy.get()
    )

    # Bind the run-scoped ContextVars through an ExitStack so set/reset stays
    # symmetric and exception-safe: if a later bind raises, the vars already
    # bound are still reset on close (the old per-token finally reset tokens
    # that may never have been set).
    stack = ExitStack()
    try:
        _bind_contextvar(stack, current_ui, effective_ui)
        _bind_contextvar(stack, current_tool_confirmation, effective_tool_confirmation)
        _bind_contextvar(stack, current_yolo, effective_yolo)
        _bind_contextvar(stack, current_hook_manager, effective_hook_manager)
        _bind_contextvar(stack, current_approval_channel, effective_approval_channel)
        _bind_contextvar(stack, current_permission_policy, effective_policy)
        _bind_contextvar(stack, current_sandbox_policy, effective_sandbox)
        # Isolate agent mode per run so concurrent runs don't share/clobber each
        # other's plan/build state; the final mode is propagated back to the
        # caller on close so an in-run mode switch persists (e.g. sticky /plan).
        mode_token, mode_parent = enter_agent_mode_scope()
        stack.callback(exit_agent_mode_scope, mode_token, mode_parent)

        effective_print_fn, effective_event_handler = _setup_print_and_events(
            print_fn, event_handler, effective_ui
        )

        effective_message = expand_prompt(message) if message else message

        effective_message, message_history, block_reason = await _run_startup_hooks(
            message,
            message_history,
            attachments,
            effective_hook_manager,
            effective_message,
        )
        if block_reason is not None:
            # A UserPromptSubmit hook blocked the prompt: end the turn before the
            # model runs, surfacing the reason as the turn's output.
            return block_reason, message_history

        prompt_content = _get_prompt_content(effective_message, attachments, print_fn)
        prompt_content = await _apply_multimodal_fallback(
            prompt_content, agent, effective_print_fn
        )
        # Append the volatile <live-context> block to the user turn. Injected
        # here rather than into the system prompt so the system prompt stays
        # byte-stable across turns and the cacheable prefix survives; the block
        # is frozen into history once written (older turns are stale snapshots).
        prompt_content = _append_live_context(prompt_content, live_context)

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
        stack.close()


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
        # Claude's startup/resume matcher: an empty history is a fresh start, a
        # populated one is a resumed/continued conversation.
        source="resume" if message_history else "startup",
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
            # Rebuild the first request via replace() instead of mutating its
            # parts in place — message_history is the history manager's cached
            # list (returned by reference), so an in-place insert would graft the
            # context onto the stored conversation and re-inject it every turn.
            first = message_history[0]
            new_first = replace(first, parts=[context_part, *first.parts])
            message_history = [new_first, *message_history[1:]]
        else:
            message_history = [ModelRequest(parts=[context_part])] + message_history

    user_prompt_results = await effective_hook_manager.execute_hooks(
        HookEvent.USER_PROMPT_SUBMIT,
        {
            "original_message": message,
            "expanded_message": effective_message,
            "attachments": attachments,
        },
        # Populate the `prompt` context field so UserPromptSubmit matchers (which
        # map to `prompt`), the CLAUDE_PROMPT env var, and the stdin payload all
        # see the submitted text — Claude-compatible.
        prompt=effective_message if effective_message is not None else message,
    )

    # Claude-compatible: a UserPromptSubmit hook may block the prompt (exit 2 /
    # decision="block") or halt all processing (continue=false). Either way the
    # turn ends before the model is called and the reason is surfaced to the user.
    block = extract_block_decision(user_prompt_results)
    if block.blocked:
        CFG.LOGGER.debug(f"USER_PROMPT_SUBMIT hook blocked the prompt: {block.reason}")
        return (
            effective_message,
            message_history,
            block.reason or "Prompt blocked by hook",
        )
    cont = extract_continue_decision(user_prompt_results)
    if cont.stop:
        CFG.LOGGER.debug(f"USER_PROMPT_SUBMIT hook halted the run: {cont.reason}")
        return (
            effective_message,
            message_history,
            cont.reason or "Stopped by hook (continue=false)",
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

    return effective_message, message_history, None


async def _prepare_history(
    agent,
    message_history,
    prompt_content,
    limiter,
    system_prompt,
    print_fn,
    effective_hook_manager,
):
    history_processors = list(getattr(agent, "zrb_history_processors", None) or [])

    # Count system prompt tokens BEFORE running processors so the summarizer
    # can account for them in its threshold comparison (the "Total" shown in
    # the usage indicator includes system prompt, not just message history).
    reserved_tokens = limiter.count_tokens(system_prompt) if system_prompt else 0
    CFG.LOGGER.debug(f"System prompt reserved tokens: {reserved_tokens}")

    # Count tokens once here so we can pass it to the hook without an extra O(n) call.
    pre_process_tokens = limiter.count_tokens(message_history)

    precompact_results = await effective_hook_manager.execute_hooks(
        HookEvent.PRE_COMPACT,
        {
            "history": message_history,
            "token_count": pre_process_tokens,
            "message_count": len(message_history),
            "has_history_processors": bool(history_processors),
        },
        # zrb compaction is threshold-driven; Claude's manual/auto matcher reads
        # this. "auto" is the only trigger today.
        trigger="auto",
    )
    # Claude-compatible: a PreCompact hook may inject additionalContext (e.g.
    # "preserve the deployment steps") ahead of summarization.
    precompact_context = extract_additional_context(precompact_results)
    if precompact_context:
        # lazy: heavy third-party
        from pydantic_ai.messages import ModelRequest, SystemPromptPart

        message_history = [
            ModelRequest(parts=[SystemPromptPart(content=precompact_context)]),
            *message_history,
        ]

    # Claude-compatible: a PreCompact hook may block compaction (exit 2 /
    # decision="block"). When blocked we skip the history processors
    # (summarization) entirely. The force-prune below is a separate context-window
    # safety net — it still runs, since an over-limit request cannot be sent to
    # the model regardless of the hook's preference.
    precompact_block = extract_block_decision(precompact_results)
    if precompact_block.blocked:
        CFG.LOGGER.debug(
            f"PRE_COMPACT hook blocked compaction: {precompact_block.reason}"
        )

    processed_history = message_history
    if not precompact_block.blocked:
        for processor in history_processors:
            processed_history = await processor(processed_history, reserved_tokens)

    processed_history = ensure_alternating_roles(processed_history)

    # PostCompact mirrors PreCompact, firing once the history processors have run.
    # A hook may inject additionalContext (prepended to the processed history) the
    # same way PreCompact does. Token count is reused from the pre-pass when no
    # processors ran (they're the only thing that changes the content).
    post_process_tokens = (
        limiter.count_tokens(processed_history)
        if history_processors
        else pre_process_tokens
    )
    postcompact_results = await effective_hook_manager.execute_hooks(
        HookEvent.POST_COMPACT,
        {
            "history": processed_history,
            "token_count": post_process_tokens,
            "message_count": len(processed_history),
            "has_history_processors": bool(history_processors),
        },
        trigger="auto",
    )
    postcompact_context = extract_additional_context(postcompact_results)
    if postcompact_context:
        # lazy: heavy third-party
        from pydantic_ai.messages import ModelRequest, SystemPromptPart

        processed_history = [
            ModelRequest(parts=[SystemPromptPart(content=postcompact_context)]),
            *processed_history,
        ]

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
    partial_run = PartialRunAccumulator()
    # pydantic-ai's before_model_request runs history processors on a shallow
    # copy of ctx.state.message_history, so any summarization it does is never
    # written back. result.all_messages() therefore always returns the original
    # (unsummarized) content. We hold a reference to the processors here so we
    # can apply them ourselves to persist their effects between tool call
    # iterations.
    history_processors = list(getattr(agent, "zrb_history_processors", None) or [])

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
                        partial_run.record_event(event)
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
                    # StopFailure: the turn is ending on an unrecoverable API
                    # error. Observe-only; guarded so a hook can never mask the
                    # original exception.
                    try:
                        await effective_hook_manager.execute_hooks(
                            HookEvent.STOP_FAILURE,
                            {"error": str(stream_error), "history": run_history},
                            error=str(stream_error),
                            error_type=classify_error_type(stream_error),
                        )
                    except Exception:
                        CFG.LOGGER.debug("StopFailure hook raised", exc_info=True)
                    raise stream_error
                current_history = outcome.new_history or current_history
                current_message = outcome.new_message
                if outcome.clear_results:
                    current_results = None
                continue

            if isinstance(result_output, DeferredToolRequests):
                CFG.LOGGER.debug(
                    "Got DeferredToolRequests, calling process_deferred_requests"
                )
                # effective_ui is typed as UIProtocol | None but by this point in
                # the loop we are past all the setup guards; the function it is
                # passed to expects a concrete UIProtocol.
                assert effective_ui is not None
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
                    # Approval is pending out-of-band: the turn suspends and
                    # control returns to the user. This is neither a turn end nor
                    # a session end, so no STOP/SESSION_END fires here; the turn
                    # resumes when the approval arrives.
                    return result_output, run_history

                current_results = rebuild_for_denials(current_results)
                current_message = None
                # Skip history processors when pending deferred results exist:
                # they can orphan the ModelResponse whose tool_calls are
                # expected by _handle_deferred_tool_results in the next stream
                # iteration.  Processor effects are already applied in
                # _prepare_history before the first stream call.
                if current_results and (
                    getattr(current_results, "calls", None)
                    or getattr(current_results, "approvals", None)
                ):
                    current_history = run_history
                else:
                    current_history = await _apply_history_processors(
                        run_history, history_processors
                    )
                CFG.LOGGER.debug("Continuing to next iteration with current_results")
                continue

            # Empty/placeholder completion guard: a weak or overloaded provider
            # sometimes returns no real text (and no tool call). Don't surface the
            # "(tool call)" placeholder as the answer — regenerate the turn a
            # bounded number of times, then raise a clear error.
            if _is_empty_completion(result_output):
                if (
                    retry_state.empty_completion_retry_count
                    < retry_state.max_empty_completion_retries
                ):
                    retry_state.empty_completion_retry_count += 1
                    print_fn(
                        "\n[SYSTEM] Model returned an empty response — retrying "
                        f"(attempt {retry_state.empty_completion_retry_count}/"
                        f"{retry_state.max_empty_completion_retries})..."
                    )
                    CFG.LOGGER.debug(
                        f"Empty completion (output={result_output!r}); "
                        "dropping the empty turn and regenerating"
                    )
                    current_history = _history_without_trailing_response(run_history)
                    current_message = None
                    current_results = None
                    result_output = None
                    continue
                raise RuntimeError(
                    "Model returned an empty response "
                    f"{retry_state.empty_completion_retry_count + 1} times. The "
                    "provider may be overloaded, or the conversation may exceed "
                    "the model's context window."
                )

            # Natural end of the agent's turn. STOP is the per-turn "done" signal
            # that Claude-Code-compatible consumers listen on (completion sounds,
            # desktop notifications, e.g. peon-ping). It is ALSO the
            # block-to-continue + systemMessage extension point: a blocking STOP
            # hook re-runs the agent with its reason injected; a systemMessage
            # hook (e.g. journaling) runs one more turn. SESSION_END is NOT fired
            # here — it is terminal, fired once when the chat session ends.
            # Manual interrupts raise CancelledError before reaching here, where
            # the TUI fires its own Stop, so the two paths never double-fire.
            stop_results = await effective_hook_manager.execute_hooks(
                HookEvent.STOP,
                {"output": result_output, "history": run_history},
                stop_hook_active=extension_state.block_count > 0,
            )
            stop_outcome = apply_turn_end_extension(
                stop_results,
                extension_state,
                result_output,
                run_history,
                print_fn,
            )
            if stop_outcome.should_continue:
                current_message = stop_outcome.new_message
                current_history = stop_outcome.new_history or current_history
                result_output = None
                current_results = None
                continue
            return resolve_extended_return(extension_state, result_output, run_history)
    except asyncio.CancelledError as ce:
        partial_run.is_interrupted = True
        setattr(ce, "zrb_partial_run", partial_run)
        raise
    except Exception as e:
        partial_run.error = str(e)
        setattr(e, "zrb_partial_run", partial_run)
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
    # lazy: zrb internal (heavy via transitive / circular)
    from zrb.llm.util.multimodal_describe import replace_unsupported_attachments

    main_model = getattr(agent, "model", None)
    return await replace_unsupported_attachments(
        prompt_content,
        main_model=main_model,
        multimodal_model=llm_config.multimodal_model,
        print_fn=print_fn,
    )
