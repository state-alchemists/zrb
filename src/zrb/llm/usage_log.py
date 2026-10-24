"""A local, append-only record of what each LLM run cost.

`RunUsage` already carries every number a cost review needs — input, output,
cache read and write, request and tool-call counts, and a `cost` when the model
is priced — but zrb printed three of those fields and kept none of them. This
module writes one JSON line per completed run, so `/usage` can answer what a
session, a day or a week consumed without asking a provider anything.

The record holds numbers only: no prompt text, no tool arguments, no file
content. That is what lets it be written by default instead of behind an opt-in
— the same reason history files are not needed to answer "what did this cost".
"""

from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.util.string.name import get_conversation_key

if TYPE_CHECKING:
    from zrb.llm.agent.types import RunUsage

_MONTH_FORMAT = "%Y-%m"
_FILE_PREFIX = "usage-"
_FILE_SUFFIX = ".jsonl"
_INT_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
    "requests",
    "tool_calls",
    "unmeasured_requests",
)
# Record field -> `RunUsage` attribute, where the two names differ.
_USAGE_ATTR = {"reasoning_tokens": "output_reasoning_tokens"}


@dataclass(frozen=True)
class UsageRecord:
    """One completed run, as it is written to the log."""

    timestamp: datetime
    model: str
    session: str
    kind: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int
    requests: int
    tool_calls: int
    unmeasured_requests: int
    duration_ms: int
    cost: float | None

    @property
    def cache_hit_ratio(self) -> float:
        """Fraction of input tokens served from the provider's prompt cache.

        The definition pydantic-ai uses (`RunUsage.cache_hit_ratio`):
        `cache_read_tokens / input_tokens`. It is a ratio rather than a
        subtraction because `input_tokens` already includes the cached reads for
        every provider, which is what makes the number comparable across them.
        """
        if not self.input_tokens:
            return 0.0
        return self.cache_read_tokens / self.input_tokens

    @property
    def session_key(self) -> str:
        """The conversation this run belongs to, stable across a rename.

        A conversation is renamed after its first message
        (`bold-arch-1234` -> `bold-arch-1234-greetings`, ADR-0109), so the
        display name in `session` cannot identify it: the first turn's row
        would be filed under a name the session no longer answers to.
        `get_conversation_key` strips the topic slug a rename appends, which
        is the same identity sub-agent transcripts and session ownership
        already key on. A run with no session name has an empty key.
        """
        return get_conversation_key(self.session)

    def to_dict(self) -> dict[str, object]:
        raw = dataclasses.asdict(self)
        raw["timestamp"] = self.timestamp.isoformat()
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> UsageRecord:
        """Rebuild a record; raises when *raw* is not one."""
        counts = {name: _as_int(raw, name) for name in _INT_FIELDS}
        return cls(
            timestamp=_as_datetime(raw["timestamp"]),
            model=str(raw["model"]),
            session=str(raw["session"]),
            kind=str(raw["kind"]),
            duration_ms=_as_int(raw, "duration_ms"),
            cost=_as_cost(raw.get("cost")),
            **counts,
        )


def usage_store_path(when: datetime, directory: str | None = None) -> str:
    """The month file a record at *when* belongs to.

    One file per month, so a week's question reads one file and a month's reads
    one — rather than one growing file that every query has to scan whole.
    """
    base = directory if directory is not None else CFG.LLM_USAGE_DIR
    return os.path.join(
        base, f"{_FILE_PREFIX}{when.strftime(_MONTH_FORMAT)}{_FILE_SUFFIX}"
    )


def record_usage(
    usage: RunUsage,
    *,
    model: str,
    session: str = "",
    kind: str = "turn",
    duration_ms: int = 0,
    when: datetime | None = None,
) -> UsageRecord | None:
    """Append one run to the log.

    Returns the record that was written, or ``None`` when the log could not be
    written — a full disk or a read-only home must not fail the turn that
    produced the numbers.
    """
    timestamp = when if when is not None else datetime.now(timezone.utc)
    if _is_empty(usage):
        return None
    record = UsageRecord(
        timestamp=timestamp,
        model=model,
        session=session,
        kind=kind,
        duration_ms=duration_ms,
        cost=_cost_of(usage),
        **{name: _count_of(usage, _USAGE_ATTR.get(name, name)) for name in _INT_FIELDS},
    )
    path = usage_store_path(timestamp)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
    except OSError:
        CFG.LOGGER.debug(f"Usage log not written: {path}", exc_info=True)
        return None
    return record


def read_records(
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    session_key: str | None = None,
    directory: str | None = None,
) -> list[UsageRecord]:
    """Every record in the window, oldest first.

    *session_key* selects one conversation by its stable key rather than its
    display name, so a conversation renamed after its first turn still
    answers for that turn (`UsageRecord.session_key`).

    A line that cannot be parsed is skipped rather than raised: one corrupt byte
    from a killed process must not make the whole history unreadable.
    """
    records: list[UsageRecord] = []
    for path in _month_files(since, until, directory):
        records.extend(_read_file(path, since, until, session_key))
    records.sort(key=lambda record: record.timestamp)
    return records


def _month_files(
    since: datetime | None, until: datetime | None, directory: str | None
) -> list[str]:
    """The month files that can hold a record inside the window.

    A bound is read as an instant, then named in UTC: files are named by the
    UTC month of the record, so local midnight on the 1st in a zone ahead of
    UTC can still belong to the previous UTC month's file (UTC+14 asks for
    January while the record sits in December).

    With no lower bound every file in the directory is a candidate and the
    upper bound is applied per record — walking forward from year 1 instead
    would build tens of thousands of month paths that cannot exist.
    """
    base = directory if directory is not None else CFG.LLM_USAGE_DIR
    if since is None:
        return _files_in(base)
    start = _as_datetime(since).astimezone(timezone.utc)
    end = (
        _as_datetime(until).astimezone(timezone.utc)
        if until is not None
        else datetime.now(timezone.utc)
    )
    candidates = [
        usage_store_path(month, base) for month in _months_between(start, end)
    ]
    return [path for path in candidates if os.path.exists(path)]


def _months_between(start: datetime, end: datetime) -> list[datetime]:
    """The first day of each month from *start* to *end*, inclusive."""
    months: list[datetime] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(datetime(year, month, 1, tzinfo=timezone.utc))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def _files_in(base: str) -> list[str]:
    """Every usage file in *base*, in name order (which is month order)."""
    try:
        names = os.listdir(base)
    except OSError:
        return []
    return [
        os.path.join(base, name)
        for name in sorted(names)
        if name.startswith(_FILE_PREFIX) and name.endswith(_FILE_SUFFIX)
    ]


def _read_file(
    path: str,
    since: datetime | None,
    until: datetime | None,
    session_key: str | None,
) -> list[UsageRecord]:
    """The records in one month file that fall inside the window."""
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return []
    records: list[UsageRecord] = []
    for line in lines:
        record = _parse_line(line)
        if record is None:
            continue
        if since is not None and record.timestamp < _as_datetime(since):
            continue
        if until is not None and record.timestamp > _as_datetime(until):
            continue
        if session_key is not None and record.session_key != session_key:
            continue
        records.append(record)
    return records


def _parse_line(line: str) -> UsageRecord | None:
    """One JSONL line as a record, or ``None`` when it is not one."""
    text = line.strip()
    if not text:
        return None
    try:
        return UsageRecord.from_dict(json.loads(text))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        CFG.LOGGER.debug(f"Skipping an unreadable usage line: {text[:80]}")
        return None


def _is_empty(usage: RunUsage) -> bool:
    """True when the run reported nothing at all — no request, no tokens.

    A provider that answers without usage data still reports the request; a
    value object carrying neither is not a run worth a line. That also keeps a
    mocked agent in a test from writing a zero row for every round.
    """
    if _count_of(usage, "requests") or _count_of(usage, "unmeasured_requests"):
        return False
    return not any(
        _count_of(usage, name)
        for name in ("input_tokens", "output_tokens", "cache_read_tokens")
    )


def _count_of(usage: RunUsage, name: str) -> int:
    """One integer field of *usage*, or 0 where the provider reported none."""
    value = getattr(usage, name, 0)
    return int(value) if isinstance(value, (int, float)) else 0


def _cost_of(usage: RunUsage) -> float | None:
    """The run's cost when pydantic-ai priced it, else ``None``.

    ``None`` is not zero: a local model has no price and an unpriced model has
    an unknown one, and `/usage` must say so rather than print a free run.
    """
    value = getattr(usage, "cost", None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(raw: dict[str, object], key: str) -> int:
    value = raw[key]
    if not isinstance(value, (int, float)):
        raise ValueError(f"{key} is not a number: {value!r}")
    return int(value)


def _as_cost(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        raise ValueError(f"cost is not a number: {value!r}")
    return float(value)


def _as_datetime(value: object) -> datetime:
    """A timezone-aware datetime; a naive one is read as UTC.

    Records are always written aware, so the normalisation is for the window
    bounds a caller passes in — comparing an aware record to a naive bound
    raises, and `/usage` must not fail because a caller left the zone off.
    """
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
