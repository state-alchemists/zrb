"""LLM agent run loop: drives `pydantic_ai.Agent`, sanitizes history, retries.

`run_agent()` binds the run's `ContextVar`s (defined in `zrb.llm.shared.agent_state`)
on entry and resets them on exit. History sanitization and the OpenAI patch
are explained in docs/technical-specs/llm-history-sanitization.md.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from collections.abc import Callable, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, cast

from zrb.config.config import CFG
from zrb.llm.agent.run.checkpoint_writer import (
    CheckpointWriter,
    create_checkpoint_writer,
    drain_checkpoints,
)
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
from zrb.llm.approval.approval_channel import current_approval_channel
from zrb.llm.config.limiter import LLMLimiter
from zrb.llm.config.model_resolver import resolve_configured_multimodal_model
from zrb.llm.hook.contracts.types import HookEvent
from zrb.llm.hook.manager import HookManager
from zrb.llm.hook.turn_evidence import (
    turn_changed_paths,
    turn_wrote_files,
)
from zrb.llm.permission.state import (
    current_permission_policy,
    enter_agent_mode_scope,
    exit_agent_mode_scope,
)
from zrb.llm.sandbox.state import current_sandbox_policy, get_effective_sandbox_policy
from zrb.llm.shared.agent_state import (
    AnyToolConfirmation,
    current_agent_run_scope,
    current_hook_manager,
    current_llm_limiter,
    current_model,
    current_multimodal_model,
    current_nested_run,
    current_small_model,
    current_tool_confirmation,
    current_ui,
    current_yolo,
    get_current_agent_run_scope,
)
from zrb.llm.shared.ambient_state import active_worktree
from zrb.llm.shared.message import ensure_alternating_roles
from zrb.llm.shared.shell_cut import (
    current_shell_cut_signal,
    get_run_shell_cut_signal,
    signal_for_run,
)
from zrb.llm.shared.stream_observer import StreamObserver, create_observed_event_handler
from zrb.llm.shared.usage_log import (
    ContextComposition,
    count_tool_calls,
    record_usage,
)
from zrb.llm.snapshot.command import run_in_worker
from zrb.llm.util.live_context_block import append_live_context
from zrb.llm.util.prompt import expand_prompt

if TYPE_CHECKING:
    from collections.abc import AsyncIterable

    from pydantic_ai import Agent, RunContext
    from pydantic_ai.agent import EventStreamHandler
    from pydantic_ai.messages import UserContent

    from zrb.llm.agent.run.typing_aliases import (
        CheckpointFn,
        History,
        PrintFn,
        PromptMessage,
        StreamEventHandler,
        UIEvent,
    )
    from zrb.llm.agent.types import RunUsage
    from zrb.llm.approval.any_approval_channel import AnyApprovalChannel
    from zrb.llm.permission.policy import PermissionPolicy
    from zrb.llm.sandbox.policy import SandboxPolicy
    from zrb.llm.ui.any_ui import AnyUI

    # What a run hands back: the model's output (typed by the agent's own
    # `output_type`, so unknowable here) and the history it produced.
    AgentRunOutput = tuple[Any, History]

# The OpenAI serialization patch is global and idempotent: apply it once per process.
_openai_patched = False


async def run_agent(
    agent: "Agent[None, Any]",
    message: str | None,
    message_history: History,
    limiter: LLMLimiter,
    attachments: Sequence[UserContent | None] | None = None,
    print_fn: PrintFn = print,
    event_handler: StreamEventHandler | None = None,
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
    permission_policy: "PermissionPolicy | None" = None,
    sandbox_policy: "SandboxPolicy | None" = None,
    checkpoint_fn: CheckpointFn | None = None,
    run_scope: str = "",
    nested: bool | None = None,
    stream_observers: "Sequence[StreamObserver] | None" = None,
) -> AgentRunOutput:
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
        # Set by `/model small|multimodal`; most UIs hold none, so readers
        # fall back to CFG on None.
        session = effective_ui.session
        bind_contextvar(stack, current_small_model, session.small_model)
        bind_contextvar(stack, current_multimodal_model, session.multimodal_model)
        # Helpers (summarizer, memory reviewer) fall back to this rather than
        # `CFG.LLM_MODEL`, which after a `/model` switch may lack credentials.
        bind_contextvar(stack, current_model, getattr(agent, "model", None))
        bind_contextvar(stack, current_llm_limiter, limiter)
        # The turn's "step aside" flag: a send-now cuts it, and the shell call
        # that is holding the turn moves its command to the background. A nested
        # run shares its parent's, so a shell inside a sub-agent is reachable by
        # the same key.
        bind_contextvar(stack, current_shell_cut_signal, signal_for_run())
        bind_contextvar(stack, current_agent_run_scope, run_scope or uuid.uuid4().hex)
        # Read by every hook payload (see HookManager.execute_hooks), so a
        # listener can tell this run's events from the turn's: a nested run has
        # no user behind it.
        bind_contextvar(stack, current_nested_run, nested_run)
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

        prepared = await _prepare_history(
            agent,
            message_history,
            prompt_content,
            limiter,
            system_prompt,
            print_fn,
            effective_hook_manager,
            # The typed message, not `prompt_content`: a fallback model may have
            # replaced an attachment with its own description of the image, and a
            # stored record must not present that as the user's words.
            typed_prompt=message or "",
        )
        current_history = prepared.history

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
            composition=prepared.composition,
        )
    finally:
        stack.close()


async def _run_startup_hooks(
    message: str | None,
    message_history: History,
    attachments: Sequence[UserContent | None] | None,
    effective_hook_manager: HookManager,
    effective_message: str | None,
) -> tuple[str | None, History, str | None]:
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


@dataclass
class _PreparedRequest:
    """One turn's history, and the sizes each stage measured on the way here.

    Carried between the four stages so none of them has to walk the history
    again to learn what the stage before it already knew. `tokens` is the
    history as it will be sent; `reserved_tokens` is what the system prompt
    costs; `message_tokens` is the user's own message.
    """

    history: History
    reserved_tokens: int = 0
    before_tokens: int = 0
    before_messages: int = 0
    stage_tokens: int = 0
    stage_messages: int = 0
    tokens: int = 0
    message_tokens: int = 0
    has_processors: bool = False

    @property
    def composition(self) -> "ContextComposition":
        """Where this request's input went, as the counter measured it."""
        return ContextComposition(
            prompt_tokens=self.reserved_tokens,
            history_tokens=self.tokens,
            message_tokens=self.message_tokens,
        )


async def _prepare_history(
    agent: "Agent[None, Any]",
    message_history: History,
    prompt_content: PromptMessage,
    limiter: LLMLimiter,
    system_prompt: str,
    print_fn: PrintFn,
    effective_hook_manager: HookManager,
    typed_prompt: str = "",
) -> "_PreparedRequest":
    """Everything between the typed message and the request the model is handed.

    Four stages, one per reason to change: reserve what the system prompt costs,
    let the history processors compact it, fit what survived into the window, and
    pace the request against the per-minute budget. The fit runs a second time
    after the POST_COMPACT hooks, because theirs is the one stage that can add to
    the history after it has been fitted.
    """
    prepared = _PreparedRequest(history=message_history)
    # Counted before the processors so the summarizer's threshold includes it.
    prepared.reserved_tokens = limiter.count_tokens(system_prompt) if system_prompt else 0
    CFG.LOGGER.debug(f"System prompt reserved tokens: {prepared.reserved_tokens}")
    await _compact_history(
        prepared, agent, limiter, typed_prompt, effective_hook_manager
    )
    _fit_history_to_window(prepared, agent, limiter, prompt_content, print_fn)
    hook_context = await _announce_compaction(
        prepared, limiter, typed_prompt, effective_hook_manager
    )
    if hook_context:
        _fit_hook_context(prepared, agent, limiter, prompt_content)
    await _pace_request(prepared, limiter, prompt_content, print_fn)
    return prepared


async def _compact_history(
    prepared: "_PreparedRequest",
    agent: "Agent[None, Any]",
    limiter: LLMLimiter,
    typed_prompt: str,
    hook_manager: HookManager,
) -> None:
    """Run the history processors, and the PRE_COMPACT hooks around them."""
    history_processors = list(getattr(agent, "zrb_history_processors", None) or [])
    prepared.has_processors = bool(history_processors)
    prepared.before_tokens = limiter.count_tokens(prepared.history)
    prepared.before_messages = len(prepared.history)

    precompact_results = await hook_manager.execute_hooks(
        HookEvent.PRE_COMPACT,
        {
            "history": prepared.history,
            # The turn that caused this, as the user typed it. It joins the history
            # only after the event, so a hook recording what was asked has nowhere
            # else to read it from -- and `prompt_content` is not the same value:
            # a fallback model may have described an attachment into it.
            "prompt": typed_prompt,
            "token_count": prepared.before_tokens,
            "message_count": prepared.before_messages,
            "has_history_processors": prepared.has_processors,
        },
        trigger="auto",
    )
    precompact_context = extract_additional_context(precompact_results)
    if precompact_context:
        prepared.history = _prepend_system_context(
            prepared.history, precompact_context
        )

    # A blocking PreCompact skips summarization; the force-prune below still
    # runs, since an over-limit request cannot be sent regardless.
    precompact_block = extract_block_decision(precompact_results)
    if precompact_block.blocked:
        CFG.LOGGER.debug(
            f"PRE_COMPACT hook blocked compaction: {precompact_block.reason}"
        )
    else:
        for processor in history_processors:
            prepared.history = await processor(prepared.history, prepared.reserved_tokens)

    prepared.history = ensure_alternating_roles(prepared.history)
    # Taken after a PreCompact hook's context joins the history, which is not history
    # that was replaced: counting it as one would hide a dropped message behind it.
    prepared.stage_tokens = limiter.count_tokens(prepared.history)
    prepared.stage_messages = len(prepared.history)
    prepared.tokens = prepared.stage_tokens


def _fit_history_to_window(
    prepared: "_PreparedRequest",
    agent: "Agent[None, Any]",
    limiter: LLMLimiter,
    prompt_content: PromptMessage,
    print_fn: PrintFn,
) -> None:
    """Force-prune a history over the limit, then trim whole turns until it fits."""
    model = getattr(agent, "model", None)
    effective_limit = max(
        0, limiter.get_effective_context_window(model) - prepared.reserved_tokens
    )
    # Before the event, so the counts describe the history that is sent. The post-compact
    # hook's own context is prepended after this, so the prune cannot drop it.
    if prepared.tokens > effective_limit:
        print_fn(
            f"\n[SYSTEM] History too large ({prepared.tokens} tokens) after summarization. Force pruning..."
        )
        safe_history: History = []
        if (
            prepared.history
            and limiter.count_tokens(prepared.history[-1]) < effective_limit
        ):
            safe_history = [prepared.history[-1]]
        prepared.history = safe_history
        prepared.tokens = limiter.count_tokens(prepared.history)

    fitted = limiter.fit_context_window(
        prepared.history, prompt_content, prepared.reserved_tokens, model=model
    )
    if len(fitted) != len(prepared.history):
        prepared.history = fitted
        prepared.tokens = limiter.count_tokens(prepared.history)


async def _announce_compaction(
    prepared: "_PreparedRequest",
    limiter: LLMLimiter,
    typed_prompt: str,
    hook_manager: HookManager,
) -> str:
    """Tell the POST_COMPACT hooks what the fit kept, and take their context.

    Answers with the context a hook added, `""` when none did: that is the one
    addition the fit has already run past.
    """
    postcompact_results = await hook_manager.execute_hooks(
        HookEvent.POST_COMPACT,
        {
            "history": prepared.history,
            "prompt": typed_prompt,
            "token_count": prepared.tokens,
            "message_count": len(prepared.history),
            # Both events fire on every turn, so a hook that records compactions has to
            # be told whether this turn replaced anything. These are the input to this
            # stage, and the counts above are what survived it.
            "before_token_count": prepared.stage_tokens,
            "before_message_count": prepared.stage_messages,
            # Fewer messages counts as a compaction even when the token total is not
            # smaller: a processor can replace many turns with one long one.
            "compacted": len(prepared.history) < prepared.stage_messages
            or prepared.tokens < prepared.stage_tokens,
            "has_history_processors": prepared.has_processors,
        },
        trigger="auto",
    )
    postcompact_context = extract_additional_context(postcompact_results)
    if not postcompact_context:
        return ""
    prepared.history = _prepend_system_context(prepared.history, postcompact_context)
    # Counted here rather than by re-walking the history: the hook's own
    # context is the only part of the request the fit has not seen.
    prepared.tokens += limiter.count_tokens(postcompact_context)
    return postcompact_context


def _fit_hook_context(
    prepared: "_PreparedRequest",
    agent: "Agent[None, Any]",
    limiter: LLMLimiter,
    prompt_content: PromptMessage,
) -> None:
    """Trim again when a POST_COMPACT hook's own context joined the history.

    The fit runs before the hooks, so the counts they are handed describe what is
    sent; that leaves the hook's context as the one part no fit has seen, and a
    hook that injects more than the fit left would put the request over the
    window, which a provider refuses outright rather than trims. The trim takes
    whole turns off the front, so an oversized injection goes with the oldest
    turns -- a request that cannot be sent helps nobody.
    """
    fitted = limiter.fit_context_window(
        prepared.history,
        prompt_content,
        prepared.reserved_tokens,
        model=getattr(agent, "model", None),
    )
    if len(fitted) != len(prepared.history):
        prepared.history = fitted
        prepared.tokens = limiter.count_tokens(prepared.history)


async def _pace_request(
    prepared: "_PreparedRequest",
    limiter: LLMLimiter,
    prompt_content: PromptMessage,
    print_fn: PrintFn,
) -> None:
    """Wait until the request about to be sent fits the per-minute budget."""
    if not prompt_content:
        return
    prepared.message_tokens = limiter.count_tokens(prompt_content)
    await _wait_for_rate_limit(
        limiter, prepared.tokens + prepared.message_tokens, print_fn
    )



def _prepend_system_context(history: History, content: str) -> History:
    """Return `history` with a system-prompt request carrying `content` in front."""
    # lazy: heavy third-party
    from pydantic_ai.messages import ModelRequest, SystemPromptPart

    return [ModelRequest(parts=[SystemPromptPart(content=content)]), *history]


async def _do_agent_run(
    agent: "Agent[None, Any]",
    cursor: TurnCursor,
    handler: "EventStreamHandler[None]",
    sandbox_deps: "SandboxPolicy | None",
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
    current_message: PromptMessage,
    current_history: History,
    print_fn: PrintFn,
    effective_event_handler: StreamEventHandler | None,
    effective_tool_confirmation: AnyToolConfirmation,
    effective_ui: AnyUI | None,
    effective_hook_manager: HookManager,
    effective_approval_channel: "AnyApprovalChannel | None",
    checkpoint_fn: CheckpointFn | None = None,
    sandbox_deps: "SandboxPolicy | None" = None,
    nested_run: bool = False,
    composition: "ContextComposition | None" = None,
) -> AgentRunOutput:
    # lazy: heavy third-party
    from pydantic_ai import DeferredToolRequests

    cursor = TurnCursor(
        history=current_history,
        message=current_message,
        run_history=current_history,
        composition=composition,
    )
    cursor.snapshot = _create_turn_snapshot(nested_run)
    retry_state = RetryState()
    extension_state = ExtensionState()
    partial_run = PartialRunAccumulator()
    checkpoint_writer = create_checkpoint_writer(checkpoint_fn)

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
                checkpoint_writer,
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
        # Drained here so a lagging write cannot land after the caller's
        # end-of-turn save.
        await drain_checkpoints(checkpoint_writer)
        if cursor.snapshot is not None:
            cursor.snapshot.close()


async def _stream_one_round(
    agent: "Agent[None, Any]",
    cursor: TurnCursor,
    partial_run: PartialRunAccumulator,
    effective_ui: AnyUI | None,
    effective_event_handler: StreamEventHandler | None,
    checkpoint_writer: "CheckpointWriter | None",
    sandbox_deps: "SandboxPolicy | None",
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
        checkpoint_writer=checkpoint_writer,
        baseline_len=cursor.round_baseline,
    )
    started_at = time.monotonic()
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
        _record_run_usage(
            result.response.model_name,
            result.usage,
            effective_ui,
            started_at,
            result.new_messages(),
            # Taken, not read: only the round that sends the prepared request
            # describes it, and this is that round the first time round.
            composition=cursor.take_composition(),
        )
        if effective_event_handler:
            await effective_event_handler(AgentRunResultEvent(result=result))
        return None
    except Exception as stream_exc:
        return _explain_usage_limit(stream_exc)
    finally:
        _set_active_run_context(effective_ui, None)


def _record_run_usage(
    model_name: str,
    usage: "RunUsage",
    effective_ui: "AnyUI | None",
    started_at: float,
    new_messages: History | None = None,
    composition: "ContextComposition | None" = None,
) -> None:
    """Write one usage-log line for the round that just finished.

    *new_messages* are this round's own messages, where each tool call and its
    result already sit, so the per-tool counts cost one pass at the end of the
    round instead of a hook on every call.

    *composition* is where this request's input went. Only the round that sends
    the prepared request has one; the others omit it rather than repeat it.

    The session name is the UI's, because that is where a conversation's
    identity lives; a headless run records an empty one and `/usage` still sees
    its tokens in the day and week windows.
    """
    session = ""
    if effective_ui is not None:
        session = effective_ui.session.conversation_session_name or ""
    calls, errors = count_tool_calls(
        new_messages if isinstance(new_messages, list) else []
    )
    record_usage(
        usage,
        model=model_name if isinstance(model_name, str) else "",
        session=session,
        duration_ms=int((time.monotonic() - started_at) * 1000),
        tool_counts=calls,
        tool_errors=errors,
        context=composition,
    )


async def _recover_from_stream_error(
    stream_error: Exception,
    retry_state: RetryState,
    cursor: TurnCursor,
    partial_run: PartialRunAccumulator,
    print_fn: PrintFn,
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
    retry_state: RetryState, cursor: TurnCursor, print_fn: PrintFn
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


def is_memory_due_for_turn() -> bool:
    """Whether a completed turn owes the memory log a line.

    Due on every completed turn while memory is on, whether or not the reviewer
    is: the line is written by a log-only hook, and switching off the per-turn
    small-model call must not also stop recording what the day held. The reviewer
    reads the same flag, and its own switch decides whether it joins.
    """
    return bool(CFG.LLM_MEMORY_ENABLED)


async def _finish_turn(
    cursor: TurnCursor,
    extension_state: ExtensionState,
    effective_hook_manager: HookManager,
    print_fn: PrintFn,
    nested_run: bool = False,
) -> AgentRunOutput | None:
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
            "memory_due": is_memory_due_for_turn(),
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
    partial_run: PartialRunAccumulator, run_history: History
) -> History:
    """The best history to attach to an unhandled run exception.

    `run_history` only updates when `agent.run()` returns; the live
    `ctx.messages` covers the whole turn, dangling tool call included (the
    caller closes it via `close_dangling_tool_calls`).
    """
    if partial_run.latest_history is not None:
        return list(partial_run.latest_history)
    return run_history


def _build_event_stream_handler(
    effective_ui: AnyUI | None,
    effective_event_handler: StreamEventHandler | None,
    partial_run: PartialRunAccumulator,
    checkpoint_writer: CheckpointWriter | None = None,
    baseline_len: int = 0,
) -> "EventStreamHandler[None]":
    """Build the `event_stream_handler` for one `agent.run()` call.

    Registers the live `RunContext` on the UI so a mid-turn message can be
    steered into this run; the caller clears it after `agent.run()`.
    `checkpoint_writer` is offered a snapshot whenever `ctx.messages` grows and
    ends in a `ModelRequest` — a structurally complete history.
    """
    last_checkpoint_len = baseline_len

    async def _handler(
        ctx: "RunContext[None]", events: AsyncIterable["UIEvent"]
    ) -> None:
        nonlocal last_checkpoint_len
        _set_active_run_context(effective_ui, ctx)
        async for event in events:
            partial_run.record_event(event)
            # Live reference for the crash/cancel fallback in `_execution_loop`.
            partial_run.latest_history = ctx.messages
            if effective_event_handler:
                await effective_event_handler(event)
            if _is_checkpoint_boundary(ctx.messages, last_checkpoint_len):
                last_checkpoint_len = len(ctx.messages)
                # A structurally complete history: the moment a message held in
                # the queue can join this turn and be read by its next request
                # (ADR-0078).
                _deliver_queued_messages(effective_ui)
                if checkpoint_writer is not None:
                    # Copy now: the source list keeps growing.
                    checkpoint_writer.submit(list(ctx.messages))

    return _handler


def _is_checkpoint_boundary(messages: History, last_checkpoint_len: int) -> bool:
    # lazy: heavy third-party
    from pydantic_ai.messages import ModelRequest

    return len(messages) > last_checkpoint_len and isinstance(
        messages[-1], ModelRequest
    )


def _deliver_queued_messages(effective_ui: AnyUI | None) -> None:
    """Hand the ready queued messages to this run, on a checkpoint boundary.

    A message typed while a turn runs joins that turn here instead of waiting
    for it to end: the history is complete, so the request being assembled reads
    it. Only entries the queue calls ready go — not the one the user is editing,
    and none inside its grace window — and nothing is interrupted, since the
    model is asking again anyway. A UI that cannot deliver (a custom one, or one
    with no queue) reports that nothing moved.

    Nothing is caught here: delivering is queue bookkeeping plus a UI's echo
    redraw, and each of those guards its own failure — swallowing a new class of
    error to keep the turn alive would hide the reason it was thrown.
    """
    if effective_ui is not None:
        effective_ui.input.deliver_queued_messages_early()


def _set_active_run_context(
    effective_ui: AnyUI | None, ctx: "RunContext[None] | None"
) -> None:
    """Best-effort: not every `AnyUI` implementer supports steering.

    The run's cut signal is published beside it, and both are read through the
    same UI the keybinding handler already has — the handler runs in the UI's
    task, where the run's context variables are not visible.
    """
    if effective_ui is None:
        return
    signal = get_run_shell_cut_signal() if ctx is not None else None
    for name, value in (("active_run_context", ctx), ("shell_cut_signal", signal)):
        try:
            setattr(effective_ui, name, value)
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


async def _wait_for_rate_limit(
    limiter: LLMLimiter,
    request_tokens: int,
    # Called with `end=""` for the in-place status line, hence not `PrintFn`.
    print_fn: Callable[..., object],
) -> None:
    """Wait until the prepared request fits the per-minute budget.

    The size arrives counted. This used to fit the history itself, so every turn
    fitted a history that had just been fitted, and walked the whole history a
    third time to estimate a request whose size the fit had already told it.
    """

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

    if request_tokens <= 0:
        return
    # No content: the size is already counted, and `acquire` takes it as given.
    await limiter.acquire(
        None, notifier=notify_throttling, estimated_tokens=request_tokens
    )


async def _apply_multimodal_fallback(
    prompt_content: PromptMessage,
    agent: "Agent[None, Any]",
    print_fn: PrintFn,
) -> PromptMessage:
    """Replace binaries the main model can't consume with text descriptions.

    Uses the multimodal model when configured; otherwise unsupported
    attachments are dropped with a warning.
    """
    # lazy: transitively heavy — multimodal_describe loads pydantic_ai, pdfplumber, prompt_toolkit
    from zrb.llm.tool.multimodal_describe import replace_unsupported_attachments

    main_model = getattr(agent, "model", None)
    return await replace_unsupported_attachments(
        cast("str | list[UserContent] | None", prompt_content),
        main_model=main_model,
        multimodal_model=resolve_configured_multimodal_model(),
        print_fn=print_fn,
    )
