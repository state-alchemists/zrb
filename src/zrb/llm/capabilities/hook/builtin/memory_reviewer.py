"""The memory reviewer: a Stop hook that writes what the turn taught.

The foreground model is busy answering; a fact that cost the turn to learn is
worth recording after the answer exists, off the critical path. The reviewer sees
one completed turn's transcript and the three memory tools, so "nothing durable"
costs one small-model call and changes nothing — which is the normal outcome.
When the day's page is full it is handed the day as well, because an append it
cannot see coming is a refusal, and a day that loses its evening is a day nobody
wrote down.

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
from datetime import datetime
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.capabilities.hook.contracts.interface import HookResult
from zrb.llm.capabilities.hook.contracts.schema import (
    AgentHookConfig,
    HookConfig,
    MatcherConfig,
)
from zrb.llm.capabilities.hook.contracts.types import (
    HookEvent,
    HookType,
    MatcherOperator,
)
from zrb.llm.contracts.config.model_resolver import resolve_configured_small_model
from zrb.llm.contracts.memory import render, store
from zrb.llm.contracts.memory.model import (
    KIND_DIARY,
    KIND_LOOP,
    body_limit,
    compact_at,
    digest_body,
    injection_reason,
)
from zrb.llm.contracts.shared.prompt_text import get_prompt
from zrb.llm.contracts.util.spoken import split_spoken

if TYPE_CHECKING:
    from collections.abc import Callable

    from zrb.llm.capabilities.hook.contracts.interface import HookCallable, HookContext
    from zrb.llm.capabilities.hook.manager import HookManager

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

# Room a day needs below the point where it must be compacted, before an append is
# worth asking for. A paragraph that lands in the day is a moment — the user's words
# quoted, then the line saying why they mattered — and 600 characters is a generous
# one. Less room than this and the append is a refusal the reviewer cannot see
# coming: it holds the transcript, not the page, so it is handed the page instead of
# being told to guess. Measured against `compact_at`, not the cap: the append is
# refused at the threshold, so the page has to arrive before it, not before it fills.
_DAY_APPEND_RESERVE = 600


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
            # The whole note: the day the turn belongs to, and the debts a turn
            # can close. One callable because the hook carries one.
            input_note=_reviewer_note,
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
            # dropped commit is silent. It matters here because this turn runs as
            # its own task beside the reviewer, and the two commit concurrently.
            #
            # The log is part of the audit trail, and a log day is the one thing
            # the store may prune: an entry that never reached git is an entry
            # retention can take with nothing left behind.
            store.git_commit(f"log: {store.today()}")
    except OSError:
        # The reply is already delivered; a log that could not be written is a
        # missing line, not a failed turn.
        return


def _without_speech_tags(line: str) -> str:
    """*line* without the `<spoken>` markers: a log line is the event, not the tags.

    Which tags are markers is not this module's question, and answering it here
    twice went wrong twice — first by stripping a quoted one, then by leaving a
    closing delimiter behind when the sentence's own full stop came after it.
    `split_spoken` already decides: a block is opened by `<spoken>` and closed by
    the next `</spoken>`, and a tag inside an inline code span is a tag being
    quoted, which stays. The log takes the shown copy of that decision.
    """
    _spoken, shown = split_spoken(line)
    return shown.strip()


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
        line = _without_speech_tags(line.lstrip(">-* ").strip())
        if not line:
            continue
        sentence = line.split(". ")[0].rstrip(".")
        return sentence[: _LOG_LINE_MAX_CHARS - 1].strip() + (
            "…" if len(sentence) >= _LOG_LINE_MAX_CHARS else ""
        )
    return ""


# How many open loops the note names. A loop that reaches the note is one this
# turn can close; one that misses it is not lost — the note says how many more
# exist and `SearchMemory` still reaches them — so the number is a budget, not
# the ledger. On a laptop whose small model is its main model, every line here
# is paid for on every turn.
_LOOPS_HANDED_OVER = 6


def _reviewer_note(context: "HookContext") -> str:
    """What the reviewer is told beyond the transcript: the day, then the loops.

    Two subjects in one note because the hook carries one note: the day this turn
    belongs to, and the debts a turn can close.
    """
    parts = (_day_note(context), _open_loops_note())
    return "\n\n".join(part for part in parts if part)


def _open_loops_note() -> str:
    """The loops still open, newest first, and the one rule for closing one.

    The prompt has said "when the turn finished something you owed, close it"
    since the hook existed, and said it against a store the reviewer could not
    see: the only way it found a loop was to search a subject it had no reason
    to suspect was owed, so a thread finished across three turns was read by
    three turns and closed by none. This is the list that makes that sentence a
    decision.
    """
    loops = sorted(
        (fact for fact in store.load_facts() if fact.kind == KIND_LOOP),
        key=lambda fact: (fact.updated, fact.id),
        reverse=True,
    )
    named = loops[:_LOOPS_HANDED_OVER]
    lines = [line for line in (render.core_line(fact) for fact in named) if line]
    if not lines:
        return ""
    rest = len(loops) - len(named)
    tail = (
        f"\n{rest} more are open and not named here; `SearchMemory` reaches them "
        "by subject."
        if rest > 0
        else ""
    )
    return (
        f"{len(loops)} loops are open, newest first. Close one only when this "
        "turn's own evidence proves it finished — a merge, a green run, a tag on "
        "the remote. A thread waiting on the user is not finished by a turn that "
        "asks about it, and one this turn only discussed stays open.\n"
        + "\n".join(lines)
        + tail
    )


def _day_note(context: "HookContext") -> str:
    """The day's date and how full its page is, and its body when it is tight.

    A day is written one paragraph per turn, so a page that fills up stops
    recording and says nothing: the append comes back refused to a reviewer that
    has the transcript and never the page, and the day loses its evening — which is
    what happened on 2026-11-17, where the body reached 7,962 of 8,000 characters
    at half past ten in the morning and did not grow again.

    The room is stated on every turn, not only when it is short, because a reserve
    is a guess: a paragraph can be longer than what is left while the page looks
    comfortable. The body is handed over only when the page is nearly full, since
    that is the one thing worth paying for every turn.

    The hour is stated with the date because the reviewer writes a narrative and
    has no other clock: given a day and no hour it names one from the shape of the
    transcript, and a review that arrives as a conversation ends reads as night.
    On 2026-11-18 three paragraphs written between six and seven in the morning
    said "late in the morning", "late in the evening" and "late in the night".

    It is stated as the hours *the turn ran*, because that is what they are: the
    review runs when the turn closes, and the payload says when it opened, so a
    turn that spent an hour on tools is dated from nine to ten rather than to ten
    alone. A note that said only "the clock reads 06:13" left the reviewer free to
    decide that clock was somebody else's, and the prompt then told it so outright
    — the hour here was the review's, not the moment's — and hours left the diary
    altogether: no page from 2026-11-16, 11-19 or 11-20 names one. A date and no
    hour is ambiguous; an hour that says which moment it belongs to is not.

    Both are read from one instant. Two reads can straddle local midnight, and the
    note would then name yesterday's day beside today's hour — a page that records
    a midnight turn under the wrong date. The turn's start is not read a second
    time for that reason: it comes from the payload, already a string.

    Read without the lock, which `store.write_document`'s rename makes safe: a
    reader never sees a document that is still being written.
    """
    at = _turn_end(context) or datetime.now().astimezone()
    day = at.date().isoformat()
    span = _turn_span(context, at)
    entry = store.load_diary(day)
    if entry is None:
        return (
            f"Today is `{day}`, and {span}. It has no diary "
            "entry yet: `claim` and `body` create one."
        )
    limit = body_limit(KIND_DIARY)
    at = compact_at(KIND_DIARY)
    room = at - len(entry.body)
    head = (
        f"Today is `{day}` and {span}; its page holds "
        f"{len(entry.body)} of {limit} characters and is compacted from {at}, so "
        f"{max(room, 0)} remain below that. A paragraph that would carry it past "
        "is written back as the whole day, not appended."
    )
    if room > _DAY_APPEND_RESERVE:
        return head
    return f"{head}\n\n{_full_day_note(day, entry.body, at)}"


def _turn_end(context: "HookContext") -> datetime | None:
    """When the turn ended, when the payload says — the review may run minutes later.

    The hook is asynchronous: a turn that ends at 23:59 can have its note built at
    00:01, and a date read from `now` files it under the next day — the one wrong
    date a reader would have to hunt for. A payload without it (an older runner, a
    test) leaves `now` the only clock there is.
    """
    data = context.event_data if isinstance(context.event_data, dict) else {}
    raw = data.get("turn_ended_at")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _turn_span(context: "HookContext", at: datetime) -> str:
    """When this turn ran, as one clause: its start only when the runner gave one.

    The Stop payload carries `turn_started_at` from the cursor, which is built
    before the first round. Without it the note says only that the turn ended, and
    a reviewer told only the end dates a request made at nine to ten — the failure
    this hour was added for, one level down: an hour that is true but belongs to
    another moment is as unchecked as an invented one.
    """
    data = context.event_data if isinstance(context.event_data, dict) else {}
    started = _clock_of(data.get("turn_started_at"))
    ended = at.strftime(_CLOCK_FORMAT)
    if started is None:
        return f"the turn just ended at {ended}"
    return f"the turn ran from {started} to {ended}"


def _clock_of(value: object) -> str | None:
    """An ISO timestamp from the payload read as `HH:MM`, or None if it is not one."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).strftime(_CLOCK_FORMAT)
    except ValueError:
        return None


def _full_day_note(day: str, body: str, at: int) -> str:
    """What the reviewer is told when the day cannot take another paragraph.

    The target is the threshold, not the cap. A rewrite asked to fit "under
    8,000" fits at 7,980 and frees nothing: the next paragraph is refused again,
    and the page reads as frozen for as long as the day lasts.
    """
    return (
        f"The page is past the point where it is compacted, so an append is "
        f"refused rather than shortened. Its body, as it stands (digest "
        f"`{digest_body(body)}`):\n\n{body}\n\n"
        "If this turn belongs in the day, write the whole day back instead: "
        f'`Remember(id="{day}", kind="diary", body_mode="w", '
        f'body_digest="{digest_body(body)}", body="…")`, with every paragraph worth '
        f"keeping plus this turn's, and the whole under {at} characters. Make room "
        "by dropping the weakest paragraph, never a moment — a quote and the line "
        "saying why it mattered stays, and so does the reason behind a decision. "
        f"A body that lands at or over {at} is refused, because it has freed "
        "nothing. Omit `claim`: a day that has one keeps it. If the rewrite is "
        "refused because the day moved, merge into the body the refusal shows you "
        "and send it once more."
    )


_CLOCK_FORMAT = "%H:%M"


def _tags(context: "HookContext") -> str:
    """`(zrb, <project>)` — where the work happened, for a human reading a day."""
    tags = ["zrb"]
    cwd = (context.cwd or "").replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    if cwd and cwd not in tags:
        tags.append(cwd)
    return ", ".join(tags)
