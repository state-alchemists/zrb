"""LLM agent run loop: drives `pydantic_ai.Agent`, sanitizes history, retries.

Binds the `current_ui`, `current_tool_confirmation`, `current_yolo`,
`current_hook_manager`, `current_agent_run_scope`, and `current_approval_channel`
`ContextVar`s on entry to `run_agent()`, resets them in `finally`. The vars
themselves are defined in `zrb.llm.agent_state` (not here, and not nested
under `zrb.llm.agent` at all — `setup.py`, which `runner.py` imports at the
top, needs them too, and so does code outside this package entirely). Every
other module reads them through the wrappers there
(re-exported from `zrb.contextvars`).

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
import uuid
from contextlib import ExitStack
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Coroutine, cast

from zrb.config.config import CFG
from zrb.llm.agent.run.deferred_calls import (
    process_deferred_requests,
    rebuild_for_denials,
)
from zrb.llm.agent.run.error_classifier import classify_error_type
from zrb.llm.agent.run.history_utils import (
    history_without_trailing_response,
    is_empty_completion,
    merge_consecutive_messages,
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
    bind_contextvar,
    log_startup,
    resolve_context_dependencies,
    setup_print_and_events,
)
from zrb.llm.agent.run.turn_cursor import TurnCursor
from zrb.llm.agent_state import (
    AnyToolConfirmation,
    current_agent_run_scope,
    current_hook_manager,
    current_multimodal_model,
    current_small_model,
    current_tool_confirmation,
    current_ui,
    current_yolo,
    get_current_multimodal_model,
)
from zrb.llm.approval.approval_channel import current_approval_channel
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.config.model_resolver import resolve_configured_multimodal_model
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.turn_evidence import turn_states_preference, turn_wrote_files
from zrb.llm.hook.types import HookEvent
from zrb.llm.message import ensure_alternating_roles
from zrb.llm.permission.state import (
    current_permission_policy,
    enter_agent_mode_scope,
    exit_agent_mode_scope,
)
from zrb.llm.prompt.live_context import append_live_context
from zrb.llm.sandbox.state import current_sandbox_policy, get_effective_sandbox_policy
from zrb.llm.tool.worktree import active_worktree
from zrb.llm.util.prompt import expand_prompt

if TYPE_CHECKING:
    from pydantic_ai import Agent

    from zrb.llm.approval.any_approval_channel import AnyApprovalChannel
    from zrb.llm.ui.any_ui import AnyUI

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
    ui: AnyUI | list[AnyUI] | None = None,
    hook_manager: HookManager | None = None,
    # None = inherit from the parent run's YOLO context (what an unconfigured
    # nested helper agent wants); False = force approval prompts even inside a
    # YOLO parent; True = skip confirmations outright.
    yolo: bool | None = None,
    approval_channel: "AnyApprovalChannel | None" = None,
    system_prompt: str = "",
    live_context: str = "",
    permission_policy: Any = None,
    sandbox_policy: Any = None,
    checkpoint_fn: Callable[[list[Any]], Coroutine[Any, Any, None]] | None = None,
    run_scope: str = "",
) -> tuple[Any, list[Any]]:
    """
    Runs the agent with rate limiting, history management, and optional CLI confirmation loop.
    Returns (result_output, new_message_history).

    `checkpoint_fn`, when given, is awaited in the background (never blocking
    the run) each time the in-progress turn reaches a safe boundary — every
    tool-call round trip, not just the end of the turn — so a caller that
    persists history sees progress well before `agent.run()` returns. See
    `_build_event_stream_handler` for the boundary rule.

    `run_scope` identifies this run to nested tools that need conversation-scoped
    state (see `current_agent_run_scope`'s docstring). Pass the session name for
    a top-level conversation, a fresh per-delegation id for a sub-agent; empty
    defaults to a fresh id so an unscoped caller stays isolated.
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
    ) = resolve_context_dependencies(
        ui, tool_confirmation, yolo, approval_channel, hook_manager
    )

    log_startup(
        tool_confirmation,
        effective_tool_confirmation,
        approval_channel,
        effective_approval_channel,
    )

    # Set the policy from the explicit arg, else keep whatever a parent run set
    # (sub-agent inheritance), else None (nothing constrained).
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
    # bound are still reset on close, and no token is reset that was never set.
    stack = ExitStack()
    try:
        bind_contextvar(stack, current_ui, effective_ui)
        bind_contextvar(stack, current_tool_confirmation, effective_tool_confirmation)
        bind_contextvar(stack, current_yolo, effective_yolo)
        bind_contextvar(stack, current_hook_manager, effective_hook_manager)
        # The UI's own `small_model`/`multimodal_model` (set by `/model small
        # ...` / `/model multimodal ...`) — None when the UI has neither, in
        # which case a reader falls back to CFG. getattr, not an AnyUI
        # method: most UIs (StdUI, a bare MultiUI) never set these.
        bind_contextvar(
            stack, current_small_model, getattr(effective_ui, "small_model", None)
        )
        bind_contextvar(
            stack,
            current_multimodal_model,
            getattr(effective_ui, "multimodal_model", None),
        )
        bind_contextvar(stack, current_agent_run_scope, run_scope or uuid.uuid4().hex)
        bind_contextvar(stack, current_approval_channel, effective_approval_channel)
        bind_contextvar(stack, current_permission_policy, effective_policy)
        bind_contextvar(stack, current_sandbox_policy, effective_sandbox)
        # Resolved once, now that current_sandbox_policy reflects this run's
        # own binding above — passed as `agent.run(deps=...)` so `sandbox_gate`
        # reads it explicitly instead of re-deriving it from ambient state at
        # every tool call (ADR-0069). Safe to freeze for the run's lifetime:
        # unlike the permission policy, nothing mutates the sandbox policy
        # mid-run.
        sandbox_deps = get_effective_sandbox_policy()
        # Backstop, not the primary contract: EnterWorktree/ExitWorktree still
        # own setting/clearing this per tool call. This only guarantees that a
        # forgotten ExitWorktree (agent forgets, run errors) can't leak the
        # worktree past this run's boundary — it restores whatever was active
        # when the run started, snapshot-and-restore rather than always "".
        bind_contextvar(stack, active_worktree, active_worktree.get())
        # Isolate agent mode per run so concurrent runs don't share/clobber each
        # other's plan/build state; the final mode is propagated back to the
        # caller on close so an in-run mode switch persists (e.g. sticky /plan).
        mode_token, mode_parent = enter_agent_mode_scope()
        stack.callback(exit_agent_mode_scope, mode_token, mode_parent)

        effective_print_fn, effective_event_handler = setup_print_and_events(
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
        prompt_content = append_live_context(prompt_content, live_context)

        current_history = await _prepare_history(
            agent,
            message_history,
            prompt_content,
            limiter,
            system_prompt,
            print_fn,
            effective_hook_manager,
        )

        current_message = merge_consecutive_messages(current_history, prompt_content)

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
            checkpoint_fn=checkpoint_fn,
            sandbox_deps=sandbox_deps,
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
        limiter,
        prompt_content,
        processed_history,
        print_fn,
        reserved_tokens,
        model=getattr(agent, "model", None),
    )


async def _do_agent_run(
    agent: "Agent[None, Any]",
    cursor: TurnCursor,
    handler: Callable[[Any, Any], Awaitable[None]],
    sandbox_deps: Any,
) -> Any:
    """Isolates the `agent.run()` call as its own function, out of
    `_execution_loop`'s `while True` loop.

    Purely a pyright-performance workaround (no behavior change): pydantic-ai's
    `Agent.run` is a heavily overloaded generic method, and pyright re-runs its
    overload resolution on every fixed-point pass of the loop's control-flow
    narrowing when this call is inlined there — that combination alone took
    ~7 minutes to check. Moving the call to its own ordinary function drops it
    to ~2 seconds.
    """
    # lazy: heavy third-party
    from pydantic_ai import UsageLimits

    return await agent.run(
        cursor.message,
        message_history=cursor.history,
        deferred_tool_results=cursor.results,
        usage_limits=UsageLimits(request_limit=_request_limit()),
        event_stream_handler=handler,
        # pydantic-ai types `deps` against the Agent's own deps_type (`None`
        # here — see create_agent's comment on why it stays pinned to None
        # for the toolsets/model_settings overloads). `sandbox_gate` reads it
        # via `ctx.deps` regardless of this static type (ADR-0069).
        deps=cast(Any, sandbox_deps),
    )


async def _execution_loop(
    agent: "Agent[None, Any]",
    current_message: Any,
    current_history: list[Any],
    print_fn: Callable[[str], Any],
    effective_event_handler: Callable[[Any], Any] | None,
    effective_tool_confirmation: AnyToolConfirmation,
    effective_ui: AnyUI | None,
    effective_hook_manager: HookManager,
    effective_approval_channel: "AnyApprovalChannel | None",
    checkpoint_fn: Callable[[list[Any]], Coroutine[Any, Any, None]] | None = None,
    sandbox_deps: Any = None,
) -> tuple[Any, list[Any]]:
    # lazy: heavy third-party
    from pydantic_ai import AgentRunResultEvent, DeferredToolRequests

    cursor = TurnCursor(
        history=current_history,
        message=current_message,
        run_history=current_history,
    )
    retry_state = RetryState()
    extension_state = ExtensionState()
    partial_run = PartialRunAccumulator()
    # Background checkpoint-save tasks fired mid-turn (see `_build_event_stream_handler`).
    # Gathered in the `finally` below so a lagging write can never race past the
    # caller's own end-of-turn save.
    pending_checkpoint_tasks: list[asyncio.Task] = []

    try:
        while True:
            cursor.begin_round(
                sanitize_history(
                    cursor.history,
                    allow_orphaned_tool_calls=(cursor.results is not None),
                )
            )
            stream_error = None
            handler = _build_event_stream_handler(
                effective_ui,
                effective_event_handler,
                partial_run,
                checkpoint_fn=checkpoint_fn,
                pending_checkpoint_tasks=pending_checkpoint_tasks,
                baseline_len=cursor.round_baseline,
            )
            try:
                # Docs: https://ai.pydantic.dev/agents/#streaming-all-events
                CFG.LOGGER.debug(f"Run started, current_results={cursor.results}")
                result = await _do_agent_run(agent, cursor, handler, sandbox_deps)
                cursor.output = result.output
                CFG.LOGGER.debug(
                    f"Got result, result_output type: {type(cursor.output)}"
                )
                cursor.run_history = sanitize_history(
                    result.all_messages(),
                    allow_orphaned_tool_calls=isinstance(
                        cursor.output, DeferredToolRequests
                    ),
                )
                # `agent.run(event_stream_handler=...)`'s handler never receives
                # a trailing result event — that's `run_stream_events()`'s own
                # addition for its consumers, synthesized after the fact from
                # the same result. Re-fire it here so usage accounting and the
                # "Requests/Tool Calls/Total" summary line keep working.
                partial_run.record_event(AgentRunResultEvent(result=result))
                if effective_event_handler:
                    await effective_event_handler(AgentRunResultEvent(result=result))
            except Exception as _stream_exc:
                stream_error = _explain_usage_limit(_stream_exc)
            finally:
                _set_active_run_context(effective_ui, None)

            if stream_error is not None:
                outcome = await handle_stream_error(
                    retry_state,
                    stream_error,
                    cursor.history,
                    cursor.message,
                    cursor.run_history,
                    print_fn,
                    min_turns=cursor.prune_floor,
                )
                if not outcome.should_retry:
                    # StopFailure: the turn is ending on an unrecoverable API
                    # error. Observe-only; guarded so a hook can never mask the
                    # original exception.
                    try:
                        await effective_hook_manager.execute_hooks(
                            HookEvent.STOP_FAILURE,
                            {"error": str(stream_error), "history": cursor.run_history},
                            error=str(stream_error),
                            error_type=classify_error_type(stream_error),
                        )
                    except Exception:
                        CFG.LOGGER.debug("StopFailure hook raised", exc_info=True)
                    raise stream_error
                cursor.history = outcome.new_history or cursor.history
                cursor.message = outcome.new_message
                if outcome.clear_results:
                    cursor.results = None
                continue

            if isinstance(cursor.output, DeferredToolRequests):
                # Commit now, before `carry_forward` below makes the next
                # iteration treat this tool call as pre-existing history
                # rather than something this turn did.
                cursor.commit_round()
                CFG.LOGGER.debug(
                    "Got DeferredToolRequests, calling process_deferred_requests"
                )
                # effective_ui is typed as AnyUI | None but by this point in
                # the loop we are past all the setup guards; the function it is
                # passed to expects a concrete AnyUI.
                assert effective_ui is not None
                cursor.results = await process_deferred_requests(
                    cursor.output,
                    effective_tool_confirmation,
                    effective_ui,
                    effective_hook_manager,
                    effective_approval_channel,
                )
                CFG.LOGGER.debug(
                    f"process_deferred_requests returned: {cursor.results}"
                )
                if cursor.results is None:
                    # Approval is pending out-of-band: the turn suspends and
                    # control returns to the user. This is neither a turn end nor
                    # a session end, so no STOP/SESSION_END fires here; the turn
                    # resumes when the approval arrives.
                    return cursor.output, cursor.run_history

                cursor.results = rebuild_for_denials(cursor.results)
                cursor.message = None
                # process_deferred_requests() always populates
                # current_results.approvals for every resolved call (approved,
                # denied, or hook-blocked alike), so history processors are never
                # reapplied here -- run_history feeds the next iteration as-is.
                # Processor effects were already applied in _prepare_history
                # before the first stream call.
                cursor.carry_forward()
                CFG.LOGGER.debug("Continuing to next iteration with current_results")
                continue

            # Empty/placeholder completion guard: a weak or overloaded provider
            # sometimes returns no real text (and no tool call). Don't surface the
            # "(tool call)" placeholder as the answer — regenerate the turn a
            # bounded number of times, then raise a clear error.
            if is_empty_completion(cursor.output):
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
                        f"Empty completion (output={cursor.output!r}); "
                        "dropping the empty turn and regenerating"
                    )
                    cursor.history = history_without_trailing_response(
                        cursor.run_history
                    )
                    cursor.message = None
                    cursor.results = None
                    cursor.output = None
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
            cursor.commit_round()
            wrote_files = turn_wrote_files(cursor.accumulated)
            stop_results = await effective_hook_manager.execute_hooks(
                HookEvent.STOP,
                {
                    "output": cursor.output,
                    "history": cursor.run_history,
                    # This turn's new messages alone, and a free (no-LLM)
                    # gate on whether they touched a file — lets an
                    # evidence-gated hook (e.g. a journal-compliance agent
                    # hook) act only on turns where it's actually warranted.
                    "turn": cursor.accumulated,
                    "wrote_files": wrote_files,
                    # Additive derived field: wrote_files OR looks like a
                    # stated preference. wrote_files itself is left unchanged
                    # for any other consumer; journal_compliance.py matches on
                    # this combined field instead, since MatcherConfig has no
                    # OR primitive (hook/matcher.py evaluates a matcher list
                    # as AND-only).
                    "journal_worthy": (
                        wrote_files or turn_states_preference(cursor.accumulated)
                    ),
                },
                stop_hook_active=extension_state.block_count > 0,
            )
            stop_outcome = apply_turn_end_extension(
                stop_results,
                extension_state,
                cursor.output,
                cursor.run_history,
                print_fn,
            )
            if stop_outcome.should_continue:
                cursor.message = stop_outcome.new_message
                cursor.history = stop_outcome.new_history or cursor.history
                cursor.output = None
                cursor.results = None
                continue
            return resolve_extended_return(
                extension_state, cursor.output, cursor.run_history
            )
    except asyncio.CancelledError as ce:
        partial_run.is_interrupted = True
        setattr(ce, "zrb_partial_run", partial_run)
        raise
    except Exception as e:
        partial_run.error = str(e)
        setattr(e, "zrb_partial_run", partial_run)
        if not hasattr(e, "zrb_history"):
            setattr(
                e,
                "zrb_history",
                _resolve_crash_history(partial_run, cursor.run_history),
            )
        raise e
    finally:
        await _await_pending_checkpoints(pending_checkpoint_tasks)


def _resolve_crash_history(
    partial_run: PartialRunAccumulator, run_history: list[Any]
) -> list[Any]:
    """The best available history to attach to an unhandled run exception.

    `run_history` only updates when an `agent.run()` call returns, so on a
    failure inside the very first call of this turn it's still the pre-turn
    baseline. `partial_run.latest_history` is the live, ever-growing
    `ctx.messages` and reflects everything done this turn, including a
    dangling trailing tool call — closed by the caller via
    `close_dangling_tool_calls`.
    """
    if partial_run.latest_history is not None:
        return list(partial_run.latest_history)
    return run_history


async def _await_pending_checkpoints(
    pending_checkpoint_tasks: list[asyncio.Task],
) -> None:
    """Drain in-flight checkpoint writes before the run truly ends.

    Guarantees a lagging background save can never land after (and clobber)
    the caller's own end-of-turn save.
    """
    if not pending_checkpoint_tasks:
        return
    checkpoint_results = await asyncio.gather(
        *pending_checkpoint_tasks, return_exceptions=True
    )
    for checkpoint_result in checkpoint_results:
        if isinstance(checkpoint_result, Exception):
            CFG.LOGGER.warning(f"Checkpoint save failed: {checkpoint_result}")


def _build_event_stream_handler(
    effective_ui: AnyUI | None,
    effective_event_handler: Callable[[Any], Any] | None,
    partial_run: PartialRunAccumulator,
    checkpoint_fn: Callable[[list[Any]], Coroutine[Any, Any, None]] | None = None,
    pending_checkpoint_tasks: list[asyncio.Task] | None = None,
    baseline_len: int = 0,
) -> Callable[[Any, Any], Awaitable[None]]:
    """Build the `event_stream_handler` for one `agent.run()` call.

    Registers the live `RunContext` on `effective_ui` for the duration of the
    call so `BaseUI`/`MultiUI._submit_user_message` can steer a mid-turn
    message into this run via `ctx.enqueue(..., priority="asap")` instead of
    queuing it. Registration is cleared by the caller once
    `agent.run()` returns or raises, not from inside here — the handler fires
    once per graph node (every model-request/tool-call round shares the same
    underlying pending-message queue), so re-registering each time is
    redundant.

    When `checkpoint_fn` is set, also fires it (as a background task, never
    awaited inline) every time `ctx.messages` grows and ends in a
    `ModelRequest` — the point right after a tool-call round trip's results
    have all landed, which is always a structurally complete history (no
    dangling `ToolCallPart`), unlike mid-response-streaming states.
    """
    last_checkpoint_len = baseline_len

    async def _handler(ctx: Any, events: Any) -> None:
        nonlocal last_checkpoint_len
        _set_active_run_context(effective_ui, ctx)
        async for event in events:
            partial_run.record_event(event)
            # Live reference (same list pydantic-ai appends to in place), kept
            # for the exception/cancellation fallback in `_execution_loop` —
            # cheap, no copy needed just to hold a pointer.
            partial_run.latest_history = ctx.messages
            if effective_event_handler:
                await effective_event_handler(event)
            if checkpoint_fn is not None and _is_checkpoint_boundary(
                ctx.messages, last_checkpoint_len
            ):
                last_checkpoint_len = len(ctx.messages)
                # Copy now, synchronously: the source list keeps growing, so the
                # background task must not observe a moving target.
                snapshot = list(ctx.messages)
                assert pending_checkpoint_tasks is not None
                pending_checkpoint_tasks.append(
                    asyncio.create_task(checkpoint_fn(snapshot))
                )

    return _handler


def _is_checkpoint_boundary(messages: list[Any], last_checkpoint_len: int) -> bool:
    # lazy: heavy third-party
    from pydantic_ai.messages import ModelRequest

    return len(messages) > last_checkpoint_len and isinstance(
        messages[-1], ModelRequest
    )


def _set_active_run_context(effective_ui: AnyUI | None, ctx: Any) -> None:
    """Best-effort: not every `AnyUI` implementer supports steering."""
    if effective_ui is None:
        return
    try:
        setattr(effective_ui, "active_run_context", ctx)
    except AttributeError:
        pass


def _request_limit() -> int | None:
    """The per-run model-request cap, or ``None`` when disabled.

    A run with no cap has no way to stop a model that has stopped converging:
    the prompt's Recovery rules tell it to change approach by the third attempt,
    but nothing enforces that, and a weak model will happily re-edit the same
    file from memory until the wall clock runs out (343 tool calls, 267 of them
    edits, was the worst observed). This is the enforcement half of that rule.
    """
    limit = CFG.LLM_MAX_REQUEST_PER_RUN
    return limit if limit > 0 else None


def _explain_usage_limit(exc: Exception) -> Exception:
    """Turn pydantic-ai's request-limit error into an actionable halt.

    Returned rather than raised so the caller keeps its existing error path:
    the swap happens before ``handle_stream_error``, which does not treat a
    ``RuntimeError`` as retryable, so the run halts instead of spending the
    retry budget re-hitting a cap it cannot get under. The partial history is
    still attached by the outer handler, so the work already done survives.
    """
    # lazy: heavy third-party
    from pydantic_ai.exceptions import UsageLimitExceeded

    if not isinstance(exc, UsageLimitExceeded):
        return exc
    return RuntimeError(
        f"Stopped after {CFG.LLM_MAX_REQUEST_PER_RUN} model requests in one run "
        f"({CFG.ENV_PREFIX}_LLM_MAX_REQUEST_PER_RUN). This cap exists to catch a "
        "run that is repeating itself rather than progressing — check the work "
        "done so far before raising it, since a higher cap on a loop that is not "
        "converging only spends more tokens. Set it to 0 to disable."
    )


async def _acquire_rate_limit(
    limiter: LLMLimiter,
    message: str | None,
    message_history: list[Any],
    print_fn: Callable[..., Any],
    reserved_tokens: int = 0,
    model: Any = None,
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
        message_history, message, reserved_tokens, model=model
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
    # lazy: zrb.llm.util.multimodal_describe transitively loads pydantic_ai,
    # pdfplumber and prompt_toolkit — deferred to keep the cold-start path cheap.
    from zrb.llm.util.multimodal_describe import replace_unsupported_attachments

    main_model = getattr(agent, "model", None)
    return await replace_unsupported_attachments(
        prompt_content,
        main_model=main_model,
        multimodal_model=resolve_configured_multimodal_model(
            get_current_multimodal_model()
        ),
        print_fn=print_fn,
    )
