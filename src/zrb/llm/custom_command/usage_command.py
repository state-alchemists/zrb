"""`/usage`: what the local log has consumed, accumulated by default.

Reads the local usage log (`zrb.llm.usage_log`) rather than asking a provider,
the way Claude Code's own `/usage` is computed from local session history. The
numbers are pydantic-ai's, recorded at the end of each run: tokens, prompt-cache
reads, request and tool-call counts, and a cost when the model is priced.

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
from zrb.llm.custom_command.usage_command_journal import render_journal_section
from zrb.llm.custom_command.usage_command_tools import (
    get_registered_tool_names,
    render_tools_section,
)
from zrb.llm.journal_usage_log import JournalEvent, read_events
from zrb.llm.usage_log import UsageRecord, read_records
from zrb.util.string.name import get_conversation_key

if TYPE_CHECKING:
    from zrb.llm.ui.any_ui import AnyUI

PERIODS = ("session", "today", "week", "all")
_DEFAULT_PERIOD = "all"
_WEEK_DAYS = 7
_MODEL_WIDTH = 32
_UNPRICED = "—"
_INPUT = "input_tokens"
_OUTPUT = "output_tokens"
_CACHE_READ = "cache_read_tokens"


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
            panel_title="Usage",
        )
        for alias in aliases
    ]


def render_usage(
    records: list[UsageRecord],
    label: str,
    events: list[JournalEvent] | None = None,
    registered_tools: list[str] | None = None,
) -> str:
    """The body for one window: its label, the table, the footer, then the
    Tools and Journal sections when the window has data for them.

    The panel draws the title, so the body opens with the window it covers
    rather than repeating the word "Usage".
    """
    if not records:
        return f"  No usage recorded for {label}."
    sections = [
        f"  {label}",
        "",
        _table(records),
        "",
        *_footer(records),
    ]
    for extra in (
        render_tools_section(
            records,
            (
                get_registered_tool_names()
                if registered_tools is None
                else registered_tools
            ),
        ),
        render_journal_section(events or []),
    ):
        if extra:
            sections.extend(["", *extra])
    return "\n".join(sections)


def _handle_usage(kwargs: dict[str, str], ui: "AnyUI | None") -> str:
    period = (kwargs.get("period") or "").strip().lower() or _DEFAULT_PERIOD
    if period not in PERIODS:
        return f"  /usage takes one of: {', '.join(PERIODS)}"
    records, label, window = _select(period, ui)
    return render_usage(
        records,
        label,
        read_events(since=window.since, session_key=window.session_key),
    )


@dataclass(frozen=True)
class _Window:
    """The bounds both logs are read with."""

    since: datetime | None = None
    session_key: str | None = None


def _select(period: str, ui: "AnyUI | None") -> tuple[list[UsageRecord], str, _Window]:
    """The records for *period*, the label that names it, and the window.

    The window is what both logs are read with, so the journal events cover
    exactly the runs in the table."""
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
    return records, label, window


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
    return ui.conversation_session_name or ""


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
    rows.extend(_row(model, runs) for model, runs in ordered)
    return "\n".join(rows)


def _row(model: str, runs: list[UsageRecord]) -> str:
    return (
        f"  {_ellipsize(model):<{_MODEL_WIDTH}}"
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


def _ellipsize(model: str) -> str:
    if len(model) <= _MODEL_WIDTH:
        return model
    return model[: _MODEL_WIDTH - 1] + "…"
