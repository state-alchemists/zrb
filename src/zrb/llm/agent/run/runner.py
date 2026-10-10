"""LLM agent run loop: drives `pydantic_ai.Agent`, sanitizes history, retries.

`run_agent()` binds the run's `ContextVar`s (defined in `zrb.llm.agent_state`)
on entry and resets them on exit. History sanitization and the OpenAI patch
are explained in docs/technical-specs/llm-history-sanitization.md.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable, Coroutine, Sequence
from contextlib import ExitStack
from dataclasses import replace
from typing import TYPE_CHECKING, Any, cast

from zrb.config.config import CFG
from zrb.llm.agent.run.deferred_calls import (
    process_deferred_requests,
    rebuild_for_denials,
)
from zrb.llm.agent.run.error_classifier import add_credential_hint, classify_error_type
from zrb.llm.agent.run.history_utils import (
    history_through_deferred_returns,
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
from zrb.llm.agent.run.turn_snapshot import TurnSnapshot
from zrb.llm.agent_state import (
    AnyToolConfirmation,
    current_agent_run_scope,
    current_hook_manager,
    current_llm_limiter,
    current_model,
    current_multimodal_model,
    current_small_model,
    current_tool_confirmation,
    current_ui,
    current_yolo,
    get_current_agent_run_scope,
)
from zrb.llm.ambient_state import active_worktree
from zrb.llm.approval.approval_channel import current_approval_channel
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.config.model_resolver import resolve_configured_multimodal_model
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.turn_evidence import (
    turn_changed_paths,
    turn_states_preference,
    turn_wrote_files,
)
from zrb.llm.hook.types import HookEvent
from zrb.llm.message import ensure_alternating_roles
from zrb.llm.permission.state import (
    current_permission_policy,
    enter_agent_mode_scope,
    exit_agent_mode_scope,
)
from zrb.llm.prompt.live_context import append_live_context
from zrb.llm.sandbox.state import current_sandbox_policy, get_effective_sandbox_policy
from zrb.llm.snapshot.command import run_in_worker
from zrb.llm.stream_observer import StreamObserver, create_observed_event_handler
from zrb.llm.util.prompt import expand_prompt

if TYPE_CHECKING:
    from pydantic_ai import Agent

    from zrb.llm.approval.any_approval_channel import AnyApprovalChannel
    from zrb.llm.ui.any_ui import AnyUI

# The OpenAI serialization patch is global and idempotent: apply it once per process.
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
    nested: bool | None = None,
    stream_observers: "Sequence[StreamObserver] | None" = None,
) -> tuple[Any, list[Any]]:
    """Run the agent with rate limiting, history management and confirmations.

    Returns (result_output, new_message_history).

    `checkpoint_fn` is fired in the background after every tool-call round
    trip, so a caller persisting history sees progress mid-turn.
    `run_scope` identifies the run to conversation-scoped tools (session name
    for a top-level chat, a per-delegation id for a sub-agent); empty means a
    fresh id. `nested` marks a delegated sub-agent's run; None infers it from
    whether another run is bound. `stream_observers` see every streamed event
    after the event handler; sub-agent runs do not inherit them.
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

    # Explicit arg, else the parent run's policy (sub-agents), else None.
    effective_policy = (
        permission_policy
        if permission_policy is not None
        else current_permission_policy.get()
    )
    # Same rule for the sandbox; None is resolved from CFG at the gate / shell tool.
    effective_sandbox = (
        sandbox_policy if sandbox_policy is not None else current_sandbox_policy.get()
    )

    # Read before this run binds its own scope below.
    nested_run = bool(get_current_agent_run_scope()) if nested is None else nested

    # ExitStack keeps set/reset symmetric: if a later bind raises, the vars
    # already bound are still reset, and no unset token is ever reset.
    stack = ExitStack()
    try:
        bind_contextvar(stack, current_ui, effective_ui)
        bind_contextvar(stack, current_tool_confirmation, effective_tool_confirmation)
        bind_contextvar(stack, current_yolo, effective_yolo)
        bind_contextvar(stack, current_hook_manager, effective_hook_manager)
        # Set by `/model small|multimodal`; most UIs lack them, so readers
        # fall back to CFG on None.
        bind_contextvar(
            stack, current_small_model, getattr(effective_ui, "small_model", None)
        )
        bind_contextvar(
            stack,
            current_multimodal_model,
            getattr(effective_ui, "multimodal_model", None),
        )
        # Helpers (summarizer, journal judge) fall back to this rather than
        # `CFG.LLM_MODEL`, which after a `/model` switch may lack credentials.
        bind_contextvar(stack, current_model, getattr(agent, "model", None))
        bind_contextvar(stack, current_llm_limiter, limiter)
        bind_contextvar(stack, current_agent_run_scope, run_scope or uuid.uuid4().hex)
        bind_contextvar(stack, current_approval_channel, effective_approval_channel)
        bind_contextvar(stack, current_permission_policy, effective_policy)
        bind_contextvar(stack, current_sandbox_policy, effective_sandbox)
        # Passed as `agent.run(deps=...)` for `sandbox_gate`; nothing mutates
        # the sandbox policy mid-run, so freezing it is safe.
        sandbox_deps = get_effective_sandbox_policy()
        # Backstop: EnterWorktree/ExitWorktree own this per tool call; this
        # restores the run-start value so a missed ExitWorktree can't leak the
        # worktree past the run.
        bind_contextvar(stack, active_worktree, active_worktree.get())
        # Per-run agent mode so concurrent runs don't clobber each other; the
        # final mode propagates back on close so an in-run switch persists.
        mode_token, mode_parent = enter_agent_mode_scope()
        stack.callback(exit_agent_mode_scope, mode_token, mode_parent)

        effective_print_fn, effective_event_handler = setup_print_and_events(
            print_fn, event_handler, effective_ui
        )
        effective_event_handler = create_observed_event_handler(
            effective_event_handler, stream_observers
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
            # A UserPromptSubmit hook blocked the prompt.
            return block_reason, message_history

        prompt_content = _get_prompt_content(effective_message, attachments, print_fn)
        prompt_content = await _apply_multimodal_fallback(
            prompt_content, agent, effective_print_fn
        )
        # On the user turn, not the system prompt, so the cacheable prefix
        # stays byte-stable across turns.
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
            nested_run=nested_run,
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
            # Not in place: message_history is the history manager's cached
            # list, so mutating it would re-inject the context every turn.
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
        # Feeds UserPromptSubmit matchers, CLAUDE_PROMPT and the stdin payload.
        prompt=effective_message if effective_message is not None else message,
    )

    # Block (exit 2 / decision="block") or halt (continue=false) both end the
    # turn before the model is called.
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

    # Counted before the processors so the summarizer's threshold includes it.
    reserved_tokens = limiter.count_tokens(system_prompt) if system_prompt else 0
    CFG.LOGGER.debug(f"System prompt reserved tokens: {reserved_tokens}")

    pre_process_tokens = limiter.count_tokens(message_history)

    precompact_results = await effective_hook_manager.execute_hooks(
        HookEvent.PRE_COMPACT,
        {
            "history": message_history,
            "token_count": pre_process_tokens,
            "message_count": len(message_history),
            "has_history_processors": bool(history_processors),
        },
        trigger="auto",
    )
    precompact_context = extract_additional_context(precompact_results)
    if precompact_context:
        message_history = _prepend_system_context(message_history, precompact_context)

    # A blocking PreCompact skips summarization; the force-prune below still
    # runs, since an over-limit request cannot be sent regardless.
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

    # Without processors the content is unchanged, so the count is reused.
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
        processed_history = _prepend_system_context(
            processed_history, postcompact_context
        )

    effective_limit = max(0, limiter.max_token_per_request - reserved_tokens)
    # ensure_alternating_roles is a no-op on well-formed history, so reusing
    # the pre-pass count when no processors ran is a safe approximation.
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


def _prepend_system_context(history: list[Any], content: str) -> list[Any]:
    """Return `history` with a system-prompt request carrying `content` in front."""
    # lazy: heavy third-party
    from pydantic_ai.messages import ModelRequest, SystemPromptPart

    return [ModelRequest(parts=[SystemPromptPart(content=content)]), *history]


async def _do_agent_run(
    agent: "Agent[None, Any]",
    cursor: TurnCursor,
    handler: Callable[[Any, Any], Awaitable[None]],
    sandbox_deps: Any,
) -> Any:
    """Call `agent.run()` outside `_execution_loop`'s loop.

    Pyright workaround: inlined in the loop, `Agent.run`'s overloads are
    re-resolved on every narrowing pass (~7 minutes to check vs ~2 seconds).
    """
    # lazy: heavy third-party
    from pydantic_ai import UsageLimits

    return await agent.run(
        cursor.message,
        message_history=cursor.history,
        deferred_tool_results=cursor.results,
        usage_limits=UsageLimits(request_limit=_request_limit()),
        event_stream_handler=handler,
        # deps_type is pinned to None (see create_agent); `sandbox_gate` reads
        # `ctx.deps` regardless.
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
    nested_run: bool = False,
) -> tuple[Any, list[Any]]:
    # lazy: heavy third-party
    from pydantic_ai import DeferredToolRequests

    cursor = TurnCursor(
        history=current_history,
        message=current_message,
        run_history=current_history,
    )
    cursor.snapshot = _create_turn_snapshot(nested_run)
    retry_state = RetryState()
    extension_state = ExtensionState()
    partial_run = PartialRunAccumulator()
    # Gathered in `finally` so a lagging write cannot land after the caller's
    # end-of-turn save.
    pending_checkpoint_tasks: list[asyncio.Task] = []

    try:
        await _take_turn_snapshot(cursor.snapshot)
        while True:
            cursor.begin_round(
                sanitize_history(
                    cursor.history,
                    allow_orphaned_tool_calls=(cursor.results is not None),
                )
            )
            stream_error = await _stream_one_round(
                agent,
                cursor,
                partial_run,
                effective_ui,
                effective_event_handler,
                checkpoint_fn,
                pending_checkpoint_tasks,
                sandbox_deps,
            )

            if stream_error is not None:
                await _recover_from_stream_error(
                    stream_error,
                    retry_state,
                    cursor,
                    partial_run,
                    print_fn,
                    effective_hook_manager,
                )
                continue

            if isinstance(cursor.output, DeferredToolRequests):
                if not await _resolve_deferred_requests(
                    cursor,
                    effective_tool_confirmation,
                    effective_ui,
                    effective_hook_manager,
                    effective_approval_channel,
                ):
                    # Approval pending out-of-band: the turn suspends (no
                    # STOP/SESSION_END) and resumes when the approval arrives.
                    return cursor.output, cursor.run_history
                continue

            # Weak or overloaded providers sometimes return no text and no
            # tool call; regenerate a bounded number of times.
            if is_empty_completion(cursor.output):
                _retry_empty_completion(retry_state, cursor, print_fn)
                continue

            cursor.commit_round()
            finished = await _finish_turn(
                cursor, extension_state, effective_hook_manager, print_fn, nested_run
            )
            if finished is not None:
                return finished
    except asyncio.CancelledError as ce:
        partial_run.is_interrupted = True
        setattr(ce, "zrb_partial_run", partial_run)
        raise
    except Exception as raised:
        e = add_credential_hint(raised)
        if e is not raised and hasattr(raised, "zrb_history"):
            setattr(e, "zrb_history", getattr(raised, "zrb_history"))
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
        if cursor.snapshot is not None:
            cursor.snapshot.close()


async def _stream_one_round(
    agent: "Agent[None, Any]",
    cursor: TurnCursor,
    partial_run: PartialRunAccumulator,
    effective_ui: AnyUI | None,
    effective_event_handler: Callable[[Any], Any] | None,
    checkpoint_fn: Callable[[list[Any]], Coroutine[Any, Any, None]] | None,
    pending_checkpoint_tasks: "list[asyncio.Task]",
    sandbox_deps: Any,
) -> Exception | None:
    """Run the agent once, recording its output on `cursor`.

    Returns the exception the stream raised, for the caller's retry decision,
    or `None` when the round produced a result.
    """
    # lazy: heavy third-party
    from pydantic_ai import AgentRunResultEvent, DeferredToolRequests

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
        CFG.LOGGER.debug(f"Got result, result_output type: {type(cursor.output)}")
        cursor.run_history = sanitize_history(
            result.all_messages(),
            allow_orphaned_tool_calls=isinstance(cursor.output, DeferredToolRequests),
        )
        # `agent.run()`'s stream handler never gets the trailing result event
        # (`run_stream_events()` synthesizes it); usage accounting needs it.
        partial_run.record_event(AgentRunResultEvent(result=result))
        if effective_event_handler:
            await effective_event_handler(AgentRunResultEvent(result=result))
        return None
    except Exception as stream_exc:
        return _explain_usage_limit(stream_exc)
    finally:
        _set_active_run_context(effective_ui, None)


async def _recover_from_stream_error(
    stream_error: Exception,
    retry_state: RetryState,
    cursor: TurnCursor,
    partial_run: PartialRunAccumulator,
    print_fn: Callable[[str], Any],
    effective_hook_manager: HookManager,
) -> None:
    """Prepare `cursor` for a retry, or raise when the error is unrecoverable."""
    # Read before the commit below clears the results: the committed turn
    # holds the approved tool's return and must stay unprunable.
    min_turns = cursor.prune_floor
    _commit_executed_deferred_results(cursor, partial_run)
    outcome = await handle_stream_error(
        retry_state,
        stream_error,
        cursor.history,
        cursor.message,
        cursor.run_history,
        print_fn,
        min_turns=min_turns,
    )
    if not outcome.should_retry:
        # Observe-only; guarded so a hook cannot mask the original exception.
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


def _commit_executed_deferred_results(
    cursor: TurnCursor, partial_run: PartialRunAccumulator
) -> None:
    """Commit a resumed round through its tool returns and drop the results.

    pydantic-ai runs approved tools before the model call that failed, so
    resending the results would run them again.
    """
    if cursor.results is None or partial_run.latest_history is None:
        return
    executed = history_through_deferred_returns(
        partial_run.latest_history, cursor.results
    )
    if executed is None:
        return
    cursor.run_history = executed
    cursor.commit_round()
    cursor.carry_forward()
    cursor.results = None


async def _resolve_deferred_requests(
    cursor: TurnCursor,
    effective_tool_confirmation: AnyToolConfirmation,
    effective_ui: AnyUI | None,
    effective_hook_manager: HookManager,
    effective_approval_channel: "AnyApprovalChannel | None",
) -> bool:
    """Run the turn's deferred tool calls and set up the next round.

    Returns False when approval is pending out-of-band, which suspends the
    turn rather than ending it.
    """
    # Before `carry_forward` makes this tool call look like prior history.
    cursor.commit_round()
    CFG.LOGGER.debug("Got DeferredToolRequests, calling process_deferred_requests")
    # Past the setup guards the UI is always resolved.
    assert effective_ui is not None
    cursor.results = await process_deferred_requests(
        cursor.output,
        effective_tool_confirmation,
        effective_ui,
        effective_hook_manager,
        effective_approval_channel,
    )
    CFG.LOGGER.debug(f"process_deferred_requests returned: {cursor.results}")
    if cursor.results is None:
        return False

    cursor.results = rebuild_for_denials(cursor.results)
    cursor.message = None
    # Every resolved call has an approval entry, so run_history feeds the next
    # iteration as-is; history processors already ran in _prepare_history.
    cursor.carry_forward()
    CFG.LOGGER.debug("Continuing to next iteration with current_results")
    return True


def _retry_empty_completion(
    retry_state: RetryState, cursor: TurnCursor, print_fn: Callable[[str], Any]
) -> None:
    """Drop the empty turn so the next round regenerates it, or give up."""
    if (
        retry_state.empty_completion_retry_count
        >= retry_state.max_empty_completion_retries
    ):
        raise RuntimeError(
            "Model returned an empty response "
            f"{retry_state.empty_completion_retry_count + 1} times. The "
            "provider may be overloaded, or the conversation may exceed "
            "the model's context window."
        )
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
    cursor.run_history = history_without_trailing_response(cursor.run_history)
    cursor.commit_round()
    cursor.carry_forward()
    cursor.message = None
    cursor.results = None
    cursor.output = None


def _create_turn_snapshot(nested_run: bool) -> TurnSnapshot | None:
    """A turn-start snapshot for self-review; nested runs rely on the parent's."""
    if not CFG.LLM_SELF_REVIEW_ENABLED or nested_run:
        return None
    return TurnSnapshot()


async def _take_turn_snapshot(snapshot: TurnSnapshot | None) -> None:
    """Snapshot the working directory; a missing cwd skips it, never failing the turn."""
    if snapshot is None:
        return
    try:
        workdir = os.getcwd()
    except OSError:
        return
    await run_in_worker(snapshot.take, workdir)


async def _finish_turn(
    cursor: TurnCursor,
    extension_state: ExtensionState,
    effective_hook_manager: HookManager,
    print_fn: Callable[[str], Any],
    nested_run: bool = False,
) -> tuple[Any, list[Any]] | None:
    """Fire STOP and settle the turn, or set up the round a hook asked for.

    A blocking STOP hook re-runs the agent with its reason; a systemMessage
    hook runs one more turn. Manual interrupts never reach here (the TUI fires
    its own Stop). Returns `(output, history)`, or `None` for another round.
    """
    wrote_files = turn_wrote_files(cursor.accumulated)
    stop_results = await effective_hook_manager.execute_hooks(
        HookEvent.STOP,
        {
            "output": cursor.output,
            "history": cursor.run_history,
            "turn": cursor.accumulated,
            "wrote_files": wrote_files,
            "changed_paths": turn_changed_paths(cursor.accumulated),
            "turn_start_snapshot": (
                cursor.snapshot.payload() if cursor.snapshot else None
            ),
            "run_scope": get_current_agent_run_scope(),
            "turn_id": cursor.turn_id,
            "nested_run": nested_run,
            # wrote_files OR a stated preference, precomputed because
            # MatcherConfig has no OR primitive (journal_compliance.py).
            "journal_worthy": (
                wrote_files or turn_states_preference(cursor.accumulated)
            ),
        },
        stop_hook_active=extension_state.block_count > 0,
        last_assistant_message=(
            cursor.output if isinstance(cursor.output, str) else None
        ),
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
        return None
    return resolve_extended_return(extension_state, cursor.output, cursor.run_history)


def _resolve_crash_history(
    partial_run: PartialRunAccumulator, run_history: list[Any]
) -> list[Any]:
    """The best history to attach to an unhandled run exception.

    `run_history` only updates when `agent.run()` returns; the live
    `ctx.messages` covers the whole turn, dangling tool call included (the
    caller closes it via `close_dangling_tool_calls`).
    """
    if partial_run.latest_history is not None:
        return list(partial_run.latest_history)
    return run_history


async def _await_pending_checkpoints(
    pending_checkpoint_tasks: list[asyncio.Task],
) -> None:
    """Drain in-flight checkpoint writes before the run ends."""
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

    Registers the live `RunContext` on the UI so a mid-turn message can be
    steered into this run; the caller clears it after `agent.run()`.
    `checkpoint_fn` fires in the background whenever `ctx.messages` grows and
    ends in a `ModelRequest` — a structurally complete history.
    """
    last_checkpoint_len = baseline_len

    async def _handler(ctx: Any, events: Any) -> None:
        nonlocal last_checkpoint_len
        _set_active_run_context(effective_ui, ctx)
        async for event in events:
            partial_run.record_event(event)
            # Live reference for the crash/cancel fallback in `_execution_loop`.
            partial_run.latest_history = ctx.messages
            if effective_event_handler:
                await effective_event_handler(event)
            if checkpoint_fn is not None and _is_checkpoint_boundary(
                ctx.messages, last_checkpoint_len
            ):
                last_checkpoint_len = len(ctx.messages)
                # Copy now: the source list keeps growing.
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
    """The per-run model-request cap, or ``None`` when disabled."""
    limit = CFG.LLM_MAX_REQUEST_PER_RUN
    return limit if limit > 0 else None


def _explain_usage_limit(exc: Exception) -> Exception:
    """Turn pydantic-ai's request-limit error into an actionable halt.

    A ``RuntimeError`` is not retryable in ``handle_stream_error``, so the run
    halts instead of re-hitting the cap.
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

    Uses the multimodal model when configured; otherwise unsupported
    attachments are dropped with a warning.
    """
    # lazy: transitively heavy — multimodal_describe loads pydantic_ai, pdfplumber, prompt_toolkit
    from zrb.llm.agent.run.multimodal_describe import replace_unsupported_attachments

    main_model = getattr(agent, "model", None)
    return await replace_unsupported_attachments(
        prompt_content,
        main_model=main_model,
        multimodal_model=resolve_configured_multimodal_model(),
        print_fn=print_fn,
    )
