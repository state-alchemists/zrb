"""`/usage`: what the local log has consumed, accumulated by default.

Reads the local usage log (`zrb.llm.shared.usage_log`) rather than asking a provider,
the way Claude Code's own `/usage` is computed from local session history. The
numbers are pydantic-ai's, recorded at the end of each run: tokens, prompt-cache
reads, request and tool-call counts, and a cost when the model is priced. A
compaction writes a line of its own (`summarization`), so the summarizer's spend
is reported beside the turns instead of disappearing into them.

One line is not from the log: the resume line reads the session's own history
and says what the next turn would cost to pick it back up (`read_resume`). Every
other number here describes a turn that has already been paid for.

No argument means every recorded run, not just this conversation — "what have I
spent" is asked far more often than "what did this conversation spend", and
`session` is one word away.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.custom_command.action_command import ActionCommand
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.custom_command.usage.memory import render_memory_section
from zrb.llm.custom_command.usage.resume import (
    FRESH_SESSION_TOKENS,
    ResumeReading,
    read_resume,
)
from zrb.llm.custom_command.usage.tools import (
    get_registered_tool_names,
    render_tools_section,
)
from zrb.llm.shared.usage_log import (
    COMPACTION_FORCED,
    KIND_SUMMARIZATION,
    UsageRecord,
    read_records,
)
from zrb.util.string.name import get_conversation_key

if TYPE_CHECKING:
    from zrb.llm.ui.any_ui import AnyUI

PERIODS = ("session", "today", "week", "all")
_DEFAULT_PERIOD = "all"
_WEEK_DAYS = 7
_MODEL_WIDTH = 32
_COMPONENT_WIDTH = 14
_UNPRICED = "—"
_INPUT = "input_tokens"
_OUTPUT = "output_tokens"
_CACHE_READ = "cache_read_tokens"
# How many fires the Compaction section names: enough to see a pattern, short
# enough that a day's worth of compactions does not bury the table above it.
_FIRE_LINES = 5


def create_usage_commands() -> list[AnyCustomCommand]:
    """One command per configured alias.

    No fallback to a default alias: `CFG.LLM_UI_COMMAND_USAGE` already carries
    `/usage`. An empty list would mean "off", as it does for every other UI
    command — though today the env knob cannot express it, because an empty
    value is read as unset (see `EnvField`), so the knob keeps its default.

    The reply is a table, and a table in the transcript scrolls away the moment
    the next turn starts, so it is drawn in a panel where the UI has one.
    """
    aliases = CFG.LLM_UI_COMMAND_USAGE
    return [
        ActionCommand(
            alias,
            _handle_usage,
            args=["period"],
            description=(
                "/usage [session|today|week|all] — tokens, cache and cost "
                "(default: every recorded run)"
            ),
            can_run_while_thinking=True,
            complete_arg=_complete_period,
            panel_title="Usage",
        )
        for alias in aliases
    ]


def _complete_period(arg_prefix: str) -> list[str]:
    """The periods that start with what has been typed, so `/usage <tab>` lists
    them instead of silently offering nothing."""
    prefix = arg_prefix.strip().lower()
    return [period for period in PERIODS if period.startswith(prefix)]


def render_usage(
    records: list[UsageRecord],
    label: str,
    registered_tools: list[str] | None = None,
    resume: ResumeReading | None = None,
) -> str:
    """The body for one window: its label, the table, the footer, then the
    resume line and the Compaction, Tools and Memory sections when each has
    data for it.

    The panel draws the title, so the body opens with the window it covers
    rather than repeating the word "Usage". A window with no runs still reports
    the store: the table describes runs, and the store needs none to exist.

    *resume* is the one line about the next turn instead of the last, and the
    only one read from the session rather than the log. It sits directly under
    the footer, where a `/usage` typed after a break asks its question before
    the per-tool and per-store detail below it; the reader decides whether to
    continue, not how a past turn broke down.

    Compaction lines stay out of the table and the footer. A compaction is not a
    turn: it is a separate charge, it is often carried by the small model
    `/model small` set, and it reads a prompt cache the turns had already left
    cold — counted in the per-model rows it would change what the cache share and
    the run count mean. It gets its own section, with the table's own columns.
    A record whose kind this version does not know stays in the turn totals:
    tokens the user paid for are worse lost than filed one section too wide.
    """
    turns = [record for record in records if record.kind != KIND_SUMMARIZATION]
    memory = render_memory_section(turns)
    if not records:
        return _no_usage(label, memory, resume)
    sections = [f"  {label}", ""]
    if turns:
        sections.extend([_table(turns), "", *_footer(turns)])
    else:
        sections.append("  No turn recorded for this window.")
    # After the table and its footer, and outside that branch: the line is about
    # the session, so a window holding only a compaction still gets it.
    resume_line = _resume_line(resume)
    if resume_line:
        sections.append(resume_line)
    for extra in (
        _component_section(records),
        _context_section(turns),
        _compaction_section(records),
        render_tools_section(
            turns,
            (
                get_registered_tool_names()
                if registered_tools is None
                else registered_tools
            ),
        ),
        memory,
    ):
        if extra:
            sections.extend(["", *extra])
    return "\n".join(sections)


def _component_section(records: list[UsageRecord]) -> list[str]:
    """Who spent the tokens, when more than one thing did.

    The table above is per model, because a model is what a provider bills for;
    this is per caller, because "the turn cost 120k" and "the memory reviewer
    cost 40k of it" are two questions about the same money. A window where
    everything was the conversation's own rounds gets no section — one row
    saying so is a line to read and nothing to learn, and every log written
    before this field existed is such a window.
    """
    grouped = _group_by_component(records)
    if len(grouped) < 2:
        return []
    total_input = _total(records, _INPUT)
    ordered = sorted(grouped.items(), key=lambda item: -_total(item[1], _INPUT))
    header = (
        f"  {'component':<{_COMPONENT_WIDTH}}{'runs':>6}{'input':>10}"
        f"{'output':>10}{'share':>7}"
    )
    return [
        "  Who spent it",
        header,
        *(
            f"    {_component_row(component, runs, total_input)}"
            for component, runs in ordered
        ),
    ]


def _component_row(
    component: str, runs: list[UsageRecord], total_input: int
) -> str:
    """One component row: its name, and the four numbers a reader compares."""
    share = f"{_total(runs, _INPUT) / total_input:.0%}" if total_input else _UNPRICED
    return (
        f"{component:<{_COMPONENT_WIDTH}}"
        f"{len(runs):>6}"
        f"{_tokens(_total(runs, _INPUT)):>10}"
        f"{_tokens(_total(runs, _OUTPUT)):>10}"
        f"{share:>7}"
    )


def _group_by_component(records: list[UsageRecord]) -> dict[str, list[UsageRecord]]:
    grouped: dict[str, list[UsageRecord]] = {}
    for record in records:
        grouped.setdefault(record.component or "other", []).append(record)
    return grouped


def _context_section(records: list[UsageRecord]) -> list[str]:
    """Where the turns' opening requests spent their input, by our own counter.

    Only the first round of a turn carries a composition — the request it
    describes is the one prepared before the loop started — so this covers the
    turns whose opening request was measured, and says how many that is. The
    provider's own input for those same requests sits beside the estimate,
    because a counter that drifts from what was billed is worth seeing. The gap
    between the two is the framing a provider adds and no local count can know.

    Tool definitions are not in it. They are constant per configuration and
    priced separately (ADR-0058), so folding them in would make a fixed cost
    look like a moving one.
    """
    parts = [
        part for part in (record.context for record in records) if part is not None
    ]
    if not parts:
        return []
    prompt = sum(part.prompt_tokens for part in parts)
    history = sum(part.history_tokens for part in parts)
    message = sum(part.message_tokens for part in parts)
    estimated = prompt + history + message
    reported = sum(
        record.input_tokens for record in records if record.context is not None
    )
    return [
        "  Where the input went",
        _context_row("system prompt", prompt, estimated),
        _context_row("history", history, estimated),
        _context_row("your message", message, estimated),
        f"    {len(parts)} turn(s) · provider reported {_tokens(reported)} for them",
    ]


def _context_row(label: str, tokens: int, total: int) -> str:
    """One row of the composition: what a part is, its tokens, and its share."""
    share = f"{tokens / total:.0%}" if total else _UNPRICED
    return f"    {label:<{_COMPONENT_WIDTH}}{_tokens(tokens):>10}{share:>7}"


def _compaction_section(records: list[UsageRecord]) -> list[str]:
    """The Compaction section: the table's columns, over the compacting runs only.

    Its own total, not a share of the table's: what the summarizer read is what
    the conversation cost to keep, and a user asking whether compaction is
    expensive wants that number beside the turn total, not buried in it. No
    header row — the table above already named these columns, and a second one
    under the heading only repeats it.
    """
    compactions = [record for record in records if record.kind == KIND_SUMMARIZATION]
    if not compactions:
        return []
    grouped = _group_by_model(compactions)
    ordered = sorted(grouped.items(), key=lambda item: -_total(item[1], _INPUT))
    wall_time = sum(record.duration_ms for record in compactions)
    return [
        "  Compaction",
        *(f"    {_row(model, runs)}" for model, runs in ordered),
        f"    {len(compactions)} compaction(s) · {_duration(wall_time)} of wall "
        "time · not counted in the table above",
        *_fire_lines(compactions),
    ]


def _fire_lines(compactions: list[UsageRecord]) -> list[str]:
    """Why each recent compaction ran — the fact its cost alone cannot show.

    Newest first and capped: a window can hold dozens, and what the trigger is
    doing now is the question worth answering. A line written before this field
    existed has no reason, and saying so is better than a reader taking it for
    a turn that wandered in.
    """
    ordered = sorted(compactions, key=lambda record: record.timestamp, reverse=True)
    lines = ["    fires (newest first)"]
    lines.extend(f"      {_fire_line(record)}" for record in ordered[:_FIRE_LINES])
    earlier = len(ordered) - _FIRE_LINES
    if earlier > 0:
        lines.append(f"      ... and {earlier} earlier")
    return lines


def _fire_line(record: UsageRecord) -> str:
    """One compaction's reason and the numbers it fired on."""
    # The default window is the whole log and it is never rotated, so a fires
    # list can span years: without the year, two same-day fires a year apart
    # read as twins and "newest first" becomes unverifiable.
    when = record.timestamp.astimezone().strftime("%Y-%m-%d %H:%M")
    detail = record.compaction
    if detail is None:
        return f"{when}  reason not recorded"
    if detail.reason == COMPACTION_FORCED:
        return f"{when}  forced · {detail.messages} message(s)"
    return (
        f"{when}  {detail.reason} · {_tokens(detail.history_tokens)} of "
        f"{_tokens(detail.allowed_tokens)} allowed · {detail.messages} of "
        f"{detail.window} message(s) · prompt {_tokens(detail.prompt_tokens)}"
    )


def _no_usage(label: str, memory: list[str], resume: ResumeReading | None) -> str:
    """The window said nothing about runs; the store may still have something.

    `writes` and `recall` are window numbers and are already absent from an
    empty record list, so what can appear here is the store as it is now. The
    resume line belongs above them for the same reason it belongs in the main
    body: it describes the session, not the window, and a `today` window read
    after midnight would otherwise keep the one line worth acting on out of the
    answer.
    """
    lines = [f"  No usage recorded for {label}."]
    for extra in (_resume_line(resume), *memory):
        if extra:
            lines.extend(["", extra])
    return "\n".join(lines)


def _handle_usage(kwargs: dict[str, str], ui: "AnyUI | None") -> str:
    period = (kwargs.get("period") or "").strip().lower() or _DEFAULT_PERIOD
    if period not in PERIODS:
        return f"  /usage takes one of: {', '.join(PERIODS)}"
    records, label = _select(period, ui)
    return render_usage(records, label, resume=read_resume(ui))


@dataclass(frozen=True)
class _Window:
    """The bounds the usage log is read with."""

    since: datetime | None = None
    session_key: str | None = None


def _select(period: str, ui: "AnyUI | None") -> tuple[list[UsageRecord], str]:
    """The records for *period* and the label that names it."""
    now = datetime.now(timezone.utc)
    if period == "today":
        window, label = _Window(since=_midnight(now)), "today"
    elif period == "week":
        since = now - timedelta(days=_WEEK_DAYS)
        window, label = _Window(since=since), f"the last {_WEEK_DAYS} days"
    elif period == "all":
        window, label = _Window(), "every recorded run"
    else:
        window, label = _session_window(ui, now)
    records = read_records(since=window.since, session_key=window.session_key)
    return records, label


def _session_window(ui: "AnyUI | None", now: datetime) -> tuple[_Window, str]:
    session = _session_of(ui)
    if session:
        # The stable key, not the display name: a conversation is renamed after
        # its first message, and the first turn's row keeps the earlier name.
        return _Window(session_key=get_conversation_key(session)), f"session {session}"
    # A headless run records no session name, so "this session" would select
    # nothing; the day is the smallest window that still means something.
    return _Window(since=_midnight(now)), "today (no session name)"


def _session_of(ui: "AnyUI | None") -> str:
    if ui is None:
        return ""
    return ui.session.conversation_session_name or ""


def _midnight(now: datetime) -> datetime:
    """Local midnight — the user's day, not UTC's."""
    local = now.astimezone()
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def _table(records: list[UsageRecord]) -> str:
    grouped = _group_by_model(records)
    ordered = sorted(grouped.items(), key=lambda item: -_total(item[1], _INPUT))
    rows = [
        f"  {'model':<{_MODEL_WIDTH}}{'runs':>6}{'input':>10}"
        f"{'output':>10}{'cache read':>12}{'cost':>10}"
    ]
    rows.extend(f"  {_row(model, runs)}" for model, runs in ordered)
    return "\n".join(rows)


def _row(model: str, runs: list[UsageRecord]) -> str:
    """One table row, without its indent: the table owns two spaces, a section four."""
    return (
        f"{_ellipsize(model):<{_MODEL_WIDTH}}"
        f"{len(runs):>6}"
        f"{_tokens(_total(runs, _INPUT)):>10}"
        f"{_tokens(_total(runs, _OUTPUT)):>10}"
        f"{_tokens(_total(runs, _CACHE_READ)):>12}"
        f"{_cost(runs):>10}"
    )


def _footer(records: list[UsageRecord]) -> list[str]:
    tool_calls = sum(record.tool_calls for record in records)
    # Wall time, not API time: the runner's timer surrounds a whole round, so it
    # includes tool execution and any wait for approval. Separating provider time
    # from that needs per-request spans, which is the tracing this does not do.
    run_ms = sum(record.duration_ms for record in records)
    lines = [
        f"  cache   {_cache_ratio(records):.0%} of input tokens came from the prompt cache",
        f"  runs    {len(records)} run(s) · {tool_calls} tool call(s) · "
        f"{_duration(run_ms)} of wall time",
    ]
    # Only a window that called tools has a batching shape to report; a plain
    # conversation would otherwise be told it batches nothing, which is true and
    # useless.
    if tool_calls:
        lines.append(
            f"  batch   {_calls_per_round(records):.1f} tool call(s) per round"
        )
    unpriced = [record for record in records if record.cost is None]
    if unpriced:
        lines.append(
            f"  cost    {len(unpriced)} run(s) unpriced — their cost is unknown, "
            "not zero"
        )
    unmeasured = sum(record.unmeasured_requests for record in records)
    if unmeasured:
        lines.append(
            f"  note    {unmeasured} request(s) reported no usage: the totals "
            "under-report them"
        )
    return lines


def _resume_line(resume: ResumeReading | None) -> str:
    """The one line about the next turn, or an empty string when none is due.

    Three facts, because deciding whether to continue needs all three: how long
    the conversation has sat, how much history is in it, and what each choice
    costs next. The resume figure is the history itself — a lapsed cache is
    re-sent whole — so it is not computed a second time.
    """
    if resume is None:
        return ""
    history = _tokens(resume.history_tokens)
    return (
        f"  {'resume':<8}last turn {_idle(resume.idle_seconds)} ago · "
        f"{history} tokens of history · ~{history} fresh to resume vs "
        f"~{_tokens(FRESH_SESSION_TOKENS)} to start over"
    )


def _group_by_model(records: list[UsageRecord]) -> dict[str, list[UsageRecord]]:
    grouped: dict[str, list[UsageRecord]] = {}
    for record in records:
        grouped.setdefault(record.model or "(unknown)", []).append(record)
    return grouped


def _total(runs: list[UsageRecord], field: str) -> int:
    return sum(getattr(record, field) for record in runs)


def _cache_ratio(records: list[UsageRecord]) -> float:
    """Cache reads over input tokens across the whole window, as pydantic-ai
    defines the ratio: `input_tokens` already includes the cached reads."""
    input_tokens = _total(records, _INPUT)
    if not input_tokens:
        return 0.0
    return _total(records, _CACHE_READ) / input_tokens


def _calls_per_round(records: list[UsageRecord]) -> float:
    """Tool calls per model request across the window.

    `requests` is the round count, so this is a measure of batching rather than
    of activity: every round re-sends the whole conversation, and calls issued
    one per round pay that body once each. Zero when nothing was measured, which
    is not the same as a perfectly unbatched window.
    """
    requests = sum(record.requests for record in records)
    if not requests:
        return 0.0
    return sum(record.tool_calls for record in records) / requests


def _cost(runs: list[UsageRecord]) -> str:
    """The priced total, marked `*` when only some runs in the row were priced."""
    priced = [record.cost for record in runs if record.cost is not None]
    if not priced:
        return _UNPRICED
    mark = "*" if len(priced) != len(runs) else ""
    return f"${sum(priced):.2f}{mark}"


def _tokens(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}k"
    return str(count)


def _duration(milliseconds: int) -> str:
    seconds = milliseconds // 1000
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _idle(seconds: float) -> str:
    """A gap between turns, coarser than `_duration`.

    A silence is read at a glance — "2h 7m" answers it, and its seconds add
    noise rather than precision; a run's wall time is the opposite, where the
    seconds are the point.
    """
    whole = max(0, int(seconds))
    if whole < 60:
        return f"{whole}s"
    minutes = whole // 60
    if minutes < 60:
        return f"{minutes}m"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m" if minutes else f"{hours}h"


def _ellipsize(model: str) -> str:
    if len(model) <= _MODEL_WIDTH:
        return model
    return model[: _MODEL_WIDTH - 1] + "…"
