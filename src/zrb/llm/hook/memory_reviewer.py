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

from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.config.model_resolver import resolve_configured_small_model
from zrb.llm.hook.schema import AgentHookConfig, HookConfig, MatcherConfig
from zrb.llm.hook.types import HookEvent, HookType, MatcherOperator
from zrb.llm.memory import store
from zrb.llm.memory.model import injection_reason
from zrb.llm.prompt.prompt import get_prompt

if TYPE_CHECKING:
    from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
    from zrb.llm.hook.manager import HookManager

_NAME = "memory-reviewer"

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
    config = build_memory_reviewer_hook_config()
    hook = manager.register_hook_config(config, source="builtin")
    if hook is None:
        return
    # Wrapped so the turn gets its log line even when the reviewer decides the
    # turn taught nothing: a day with no events is a day that never happened.
    manager.remove_hook(hook)
    manager.add_hook(_with_log_line(hook), config.events, config)


def _with_log_line(hook: "HookCallable") -> "HookCallable":
    async def reviewed(context: "HookContext") -> "HookResult":
        # The log line is about the turn, not about the reviewer: a failed or
        # timed-out reviewer must not leave the day with a gap, and the event was
        # already true before the reviewer ran.
        try:
            return await hook(context)
        finally:
            _append_event_line(context)

    return reviewed


def _append_event_line(context: "HookContext") -> None:
    """Append what the turn was, taken from the reply's own first sentence."""
    text = _first_sentence(context.last_assistant_message or "")
    if not text:
        return
    reason = injection_reason(text)
    if reason:
        text = WITHHELD_LOG_TEXT
    try:
        with store.locked():
            store.append_log(text, tags=_tags(context))
            store.prune_logs()
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
    cwd = (context.cwd or "").rstrip("/").rsplit("/", 1)[-1]
    if cwd and cwd not in tags:
        tags.append(cwd)
    return ", ".join(tags)
