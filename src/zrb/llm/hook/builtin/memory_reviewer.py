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
    from zrb.llm.hook.contracts.interface import HookCallable, HookContext
    from zrb.llm.hook.manager import HookManager

_NAME = "memory-reviewer"

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
    """Register the reviewer unless memory or the reviewer is switched off."""
    if not CFG.LLM_MEMORY_ENABLED or not CFG.LLM_MEMORY_REVIEWER_ENABLED:
        return
    # A cancelled turn never reaches the reviewer's matcher: the TUI fires its own
    # Stop, with `turn_cancelled` and no completed transcript.
    #
    # Registered with the reviewer rather than on `LLM_MEMORY_ENABLED` alone, even
    # though it calls no model: the log line for a *completed* turn is written by
    # `_with_log_line`, which exists only past this return, and the runner reports
    # `memory_due` false in the same configuration. An interrupt line without those
    # would leave a day whose log held cancellations and nothing else, which reads
    # worse than a day with no log at all.
    # Registered through the registry rather than with `add_hook` directly: a
    # factory is called on every load and reload, and the registry is what
    # refuses a second hook of the same name — a bare `add_hook` here would
    # append a duplicate per reload and write the line twice.
    interrupt_config = build_interrupt_log_hook_config()
    registered = manager.register_hook_config(interrupt_config, source="builtin")
    if registered is not None:
        manager.remove_hook(registered)
        manager.add_hook(
            create_interrupt_log_hook(), interrupt_config.events, interrupt_config
        )
    config = build_memory_reviewer_hook_config()
    hook = manager.register_hook_config(config, source="builtin")
    if hook is None:
        return
    # Wrapped so the turn gets its log line even when the reviewer decides the
    # turn taught nothing: a day with no events is a day that never happened.
    manager.remove_hook(hook)
    manager.add_hook(_with_log_line(hook), config.events, config)


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
        config=AgentHookConfig(
            system_prompt=get_prompt("memory_reviewer"),
            tools=["SearchMemory", "Remember", "Forget"],
            model=resolve_configured_small_model(),
            auto_approve=True,
        ),
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


def create_interrupt_log_hook() -> "HookCallable":
    """Write the interrupted turn's event line and nothing else."""

    async def interrupt_log(context: "HookContext") -> "HookResult":
        # Off the loop: the store's lock polls and the git commit can block, and a
        # quit must not hold the event loop on either while it is torn down.
        await asyncio.to_thread(_write_log_line, context, INTERRUPTED_LOG_TEXT)
        return HookResult()

    return interrupt_log


def _with_log_line(hook: "HookCallable") -> "HookCallable":
    async def reviewed(context: "HookContext") -> "HookResult":
        # The log line is about the turn, not about the reviewer: a failed or
        # timed-out reviewer must not leave the day with a gap, and the event was
        # already true before the reviewer ran.
        try:
            return await hook(context)
        finally:
            # Off the loop, for the same reason the interrupt hook is: a lock wait
            # or a slow git commit must not stall the turn that just finished.
            await asyncio.to_thread(_append_event_line, context)

    return reviewed


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
    except OSError:
        # The reply is already delivered; a log that could not be written is a
        # missing line, not a failed turn.
        return
    # The log is part of the audit trail, and a log day is the one thing the
    # store may prune: an entry that never reached git is an entry retention can
    # take with nothing left behind.
    store.git_commit(f"log: {store.today()}")


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
    cwd = (context.cwd or "").rstrip("/").rsplit("/", 1)[-1]
    if cwd and cwd not in tags:
        tags.append(cwd)
    return ", ".join(tags)
