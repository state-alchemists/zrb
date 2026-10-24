"""`/usage`: what this session, today or this week consumed.

Reads the local usage log (`zrb.llm.usage_log`) rather than asking a provider,
the way Claude Code's own `/usage` is computed from local session history. The
numbers are pydantic-ai's, recorded at the end of each run: tokens, prompt-cache
reads, request and tool-call counts, and a cost when the model is priced.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.custom_command.action_command import ActionCommand
from zrb.llm.custom_command.any_custom_command import AnyCustomCommand
from zrb.llm.usage_log import UsageRecord, read_records

if TYPE_CHECKING:
    from zrb.llm.ui.any_ui import AnyUI

PERIODS = ("session", "today", "week", "all")
_WEEK_DAYS = 7
_MODEL_WIDTH = 32
_UNPRICED = "—"
_INPUT = "input_tokens"
_OUTPUT = "output_tokens"
_CACHE_READ = "cache_read_tokens"


def create_usage_commands() -> list[AnyCustomCommand]:
    """One command per configured alias."""
    aliases = CFG.LLM_UI_COMMAND_USAGE or ["/usage"]
    return [
        ActionCommand(
            alias,
            _handle_usage,
            args=["period"],
            description=(
                "/usage [session|today|week|all] — tokens, cache and cost so far"
            ),
            can_run_while_thinking=True,
        )
        for alias in aliases
    ]


def render_usage(records: list[UsageRecord], label: str) -> str:
    """The whole reply for one window."""
    if not records:
        return f"  No usage recorded for {label}."
    sections = [
        f"  Usage — {label}",
        "",
        _table(records),
        "",
        *_footer(records),
    ]
    return "\n".join(sections)


def _handle_usage(kwargs: dict[str, str], ui: "AnyUI | None") -> str:
    period = (kwargs.get("period") or "").strip().lower() or "session"
    if period not in PERIODS:
        return f"  /usage takes one of: {', '.join(PERIODS)}"
    records, label = _select(period, ui)
    return render_usage(records, label)


def _select(period: str, ui: "AnyUI | None") -> tuple[list[UsageRecord], str]:
    """The records for *period* and the label that names it."""
    now = datetime.now(timezone.utc)
    if period == "today":
        return read_records(since=_midnight(now)), "today"
    if period == "week":
        since = now - timedelta(days=_WEEK_DAYS)
        return read_records(since=since), f"the last {_WEEK_DAYS} days"
    if period == "all":
        return read_records(), "every recorded run"
    session = _session_of(ui)
    if session:
        return read_records(session=session), f"session {session}"
    # A headless run records no session name, so "this session" would select
    # nothing; the day is the smallest window that still means something.
    return read_records(since=_midnight(now)), "today (no session name)"


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
    ordered = sorted(
        grouped.items(), key=lambda item: -_total(item[1], _INPUT)
    )
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
    model_ms = sum(record.duration_ms for record in records)
    lines = [
        f"  cache   {_cache_ratio(records):.0%} of input tokens came from the prompt cache",
        f"  runs    {len(records)} run(s) · {tool_calls} tool call(s) · "
        f"{_duration(model_ms)} of model time",
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
