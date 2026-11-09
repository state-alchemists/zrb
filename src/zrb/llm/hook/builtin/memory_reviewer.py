"""The memory reviewer: a Stop hook that writes what the turn taught.

The foreground model is busy answering; a fact that cost the turn to learn is
worth recording after the answer exists, off the critical path. The reviewer sees
one completed turn's transcript and the three memory tools, so "nothing durable"
costs one small-model call and changes nothing — which is the normal outcome.

The log line is appended here rather than by the model. The journal's lesson was
that a hook on a conversation event can describe the conversation and nothing
else: an event log is exactly what a hook can honestly write, while the *day* is
not, which is why the diary stays the reviewer's to author.

The reviewer is fire-and-forget. Nothing downstream sees whether it ran, so a run
that returns nothing is indistinguishable from a run that decided to record
nothing, and neither is an error.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.config.model_resolver import resolve_configured_small_model
from zrb.llm.hook.contracts.interface import HookResult
from zrb.llm.hook.contracts.schema import AgentHookConfig, HookConfig, MatcherConfig
from zrb.llm.hook.contracts.types import HookEvent, HookType, MatcherOperator
from zrb.llm.memory import store
from zrb.llm.memory.model import injection_reason
from zrb.llm.prompt.prompt import get_prompt

if TYPE_CHECKING:
    from collections.abc import Callable

    from zrb.llm.hook.contracts.interface import HookCallable, HookContext
    from zrb.llm.hook.manager import HookManager

_NAME = "memory-reviewer"

# The log-only hook a completed turn runs. It writes the day's event line and
# calls no model, so it is registered whenever memory is on — the reviewer's
# switch decides whether a turn is re-read, not whether it happened.
_COMPLETED_NAME = "memory-event-log"

# The log-only hook a cancelled turn runs. Separate from the reviewer because a
# cancelled turn is not a completed one: the reviewer's premise is a finished
# transcript, and what exists here is whatever streamed before the interrupt.
_INTERRUPT_NAME = "memory-interrupt-log"

# What a cancelled turn leaves in the log. It does not claim the turn had no
# reply: `cancel_current_turn` sees a queued job that is still finishing, so a
# turn whose answer already landed can also be cancelled, and the reviewer has
# written its own line for it. "Cancelled" is true in both cases; "interrupted
# before a reply" would be false in the second.
INTERRUPTED_LOG_TEXT = "the turn was cancelled"

# A tool-calling round trip takes ~15s on a small model; shutdown waits this long
# before cancelling, so a one-shot `zrb llm chat` does not kill the reviewer.
_TIMEOUT_SECONDS = 90

# The log line's text, taken from the reply's first sentence. Long enough to
# recognise the turn, short enough that twenty of them fit one day file.
_LOG_LINE_MAX_CHARS = 140

# What the log holds instead of a reply whose text reads as an instruction. That
# text would be quoted back inside a later `<memory>` block, so the log is the one
# place where the assistant's own output can become a persistent payload; the
# event stays, the words do not.
WITHHELD_LOG_TEXT = "a reply was kept out of the log: its text reads as an instruction"


def build_memory_reviewer_hook_config() -> HookConfig:
    """The reviewer's `HookConfig`, on the configured small model."""
    return HookConfig(
        name=_NAME,
        events=[HookEvent.STOP],
        type=HookType.AGENT,
        config=AgentHookConfig(
            system_prompt=get_prompt("memory_reviewer"),
            tools=["SearchMemory", "Remember", "Forget"],
            # The small model: reviewing is distillation, and a model that did not
            # write the turn reads it with fewer of its blind spots.
            model=resolve_configured_small_model(),
            # A reviewer nobody answers must not defer its own write: this hook
            # runs off the critical path with no UI, so a `Remember` that asks is
            # a fact that is never recorded. Its tool list is the three memory
            # verbs above, so approving every call it makes approves nothing else.
            auto_approve=True,
        ),
        matchers=[
            MatcherConfig(
                # Every completed turn — computed in the runner because this is
                # a constant, and a matcher has no "always" operator.
                field="event_data.memory_due",
                operator=MatcherOperator.EQUALS,
                value=True,
            )
        ],
        is_async=True,
        timeout=_TIMEOUT_SECONDS,
    )


def register_memory_reviewer_hook(manager: "HookManager") -> None:
    """Register the memory hooks the configuration asks for.

    Three hooks live here and only one calls a model. The two log hooks — a
    completed turn's event line and a cancelled turn's — are on whenever memory
    is, because the day's record is not the reviewer's business; the reviewer
    joins them when `LLM_MEMORY_REVIEWER_ENABLED` says so.

    They used to share the reviewer's switch, on the argument that a log written
    beside a reviewer that never ran would leave a day holding cancellations and
    nothing else. That was backwards: the answer was to free the line from the
    reviewer, not to drag it down with it — switching off a per-turn model call
    should not also stop recording what the day held.
    """
    if not CFG.LLM_MEMORY_ENABLED:
        return
    _register_log_hook(
        manager, build_completed_log_hook_config(), create_completed_log_hook
    )
    _register_log_hook(
        manager, build_interrupt_log_hook_config(), create_interrupt_log_hook
    )
    if CFG.LLM_MEMORY_REVIEWER_ENABLED:
        manager.register_hook_config(
            build_memory_reviewer_hook_config(), source="builtin"
        )


def _register_log_hook(
    manager: "HookManager",
    config: HookConfig,
    factory: "Callable[[], HookCallable]",
) -> None:
    """Register *config* with the callable *factory* builds, once per manager.

    The name check is what makes "once" true: `register_hook_config` does not
    refuse a duplicate — it returns `None` only for a disabled config — so a
    second scan would append a second copy and write every line twice. A fresh
    manager never repeats the factory, but `search_dirs` can be reassigned on a
    live one (its docstring invites exactly that), which clears `_loaded` and
    re-scans without clearing the registry.

    The callable is swapped in afterwards because a log hook names an
    `AgentHookConfig` for the manager's sake and must never build an agent.
    """
    if config.name in manager.registry.get_configs():
        return
    registered = manager.register_hook_config(config, source="builtin")
    if registered is None:
        return
    manager.remove_hook(registered)
    manager.add_hook(factory(), config.events, config)


def build_interrupt_log_hook_config() -> HookConfig:
    """The hook a cancelled turn runs: one event line, no model call.

    The `AgentHookConfig` is the shape `HookManager.add_hook` expects for a
    built-in; the callable registered beside it is what runs, and it never builds
    an agent. Nothing here may fail the teardown of a chat the user already quit.
    """
    return HookConfig(
        name=_INTERRUPT_NAME,
        events=[HookEvent.STOP],
        type=HookType.AGENT,
        config=_no_model_agent_config(),
        matchers=[
            MatcherConfig(
                field="event_data.turn_cancelled",
                operator=MatcherOperator.EQUALS,
                value=True,
            )
        ],
        is_async=True,
        # No model is called, so this hook must not stretch the exit drain: the
        # manager extends it to a pending agent hook's own timeout, and 90 s of
        # "the terminal looks hung after quitting" is longer than the line is
        # worth. The write runs in a thread and finishes even if the awaiting
        # task is cancelled at the ordinary budget.
        timeout=None,
    )


def build_completed_log_hook_config() -> HookConfig:
    """The hook a completed turn runs: one event line, no model call.

    Registered separately from the reviewer so the line survives
    `LLM_MEMORY_REVIEWER_ENABLED=off`: the event happened before any reviewer ran,
    and whether the turn is worth reviewing is not the same question as whether it
    happened at all.
    """
    return HookConfig(
        name=_COMPLETED_NAME,
        events=[HookEvent.STOP],
        type=HookType.AGENT,
        config=_no_model_agent_config(),
        matchers=[
            MatcherConfig(
                # Every completed turn — computed in the runner because this is
                # a constant, and a matcher has no "always" operator.
                field="event_data.memory_due",
                operator=MatcherOperator.EQUALS,
                value=True,
            )
        ],
        is_async=True,
        timeout=None,
    )


def _no_model_agent_config() -> AgentHookConfig:
    """The shape an agent hook needs to register, for a hook that builds no agent."""
    return AgentHookConfig(
        system_prompt=get_prompt("memory_reviewer"),
        tools=["SearchMemory", "Remember", "Forget"],
        model=resolve_configured_small_model(),
        auto_approve=True,
    )


def create_completed_log_hook() -> "HookCallable":
    """Write the completed turn's event line and nothing else."""

    async def completed_log(context: "HookContext") -> "HookResult":
        # Off loop, for the same reason the interrupt hook is: a lock wait or a
        # slow git commit must not stall the turn that just finished.
        await asyncio.to_thread(_append_event_line, context)
        return HookResult()

    return completed_log


def create_interrupt_log_hook() -> "HookCallable":
    """Write the interrupted turn's event line and nothing else."""

    async def interrupt_log(context: "HookContext") -> "HookResult":
        # Off the loop: the store's lock polls and the git commit can block, and a
        # quit must not hold the event loop on either while it is torn down.
        await asyncio.to_thread(_write_log_line, context, INTERRUPTED_LOG_TEXT)
        return HookResult()

    return interrupt_log


def _append_event_line(context: "HookContext") -> None:
    """Append what the turn was, taken from the reply's own first sentence."""
    text = _first_sentence(context.last_assistant_message or "")
    if not text:
        return
    _write_log_line(context, text)


def _write_log_line(context: "HookContext", text: str) -> None:
    """Put one event into the day's log, with the project it happened in.

    Split from `_append_event_line` because a turn that was cancelled has no
    reply to take a sentence from: its line is a fixed statement of the event,
    and it reaches the same file through the same lock and the same commit.
    """
    if injection_reason(text):
        text = WITHHELD_LOG_TEXT
    try:
        with store.locked():
            store.append_log(text, tags=_tags(context))
            store.prune_logs()
            # Inside the lock, like the memory tools' commits: `git_commit`
            # stages every managed path, so a commit made outside it can sweep up
            # a writer's half-finished change, or lose the race for
            # `.git/index.lock` and be dropped — this is best effort, and a
            # dropped commit is silent. It matters now because this turn runs as
            # its own task beside the reviewer, and the two commit concurrently
            # where one hook used to do both.
            #
            # The log is part of the audit trail, and a log day is the one thing
            # the store may prune: an entry that never reached git is an entry
            # retention can take with nothing left behind.
            store.git_commit(f"log: {store.today()}")
    except OSError:
        # The reply is already delivered; a log that could not be written is a
        # missing line, not a failed turn.
        return


def _first_sentence(message: str) -> str:
    """The reply's first sentence, flattened to one line and bounded.

    A reply may open with a heading, a code fence or a list marker. Those are
    skipped rather than turned into a log line: an event log records what
    happened, and "## Outcome" says nothing happened.
    """
    in_fence = False
    for raw in message.splitlines():
        line = raw.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line or line.startswith("#"):
            continue
        line = line.lstrip(">-* ").strip()
        if not line:
            continue
        sentence = line.split(". ")[0].rstrip(".")
        return sentence[: _LOG_LINE_MAX_CHARS - 1].strip() + (
            "…" if len(sentence) >= _LOG_LINE_MAX_CHARS else ""
        )
    return ""


def _tags(context: "HookContext") -> str:
    """`(zrb, <project>)` — where the work happened, for a human reading a day."""
    tags = ["zrb"]
    cwd = (context.cwd or "").replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    if cwd and cwd not in tags:
        tags.append(cwd)
    return ", ".join(tags)
