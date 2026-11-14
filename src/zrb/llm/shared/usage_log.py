"""A local, append-only record of what each LLM run cost.

`RunUsage` carries every number a cost review needs — input, output, cache read
and write, request and tool-call counts, and a `cost` when the model is priced.
This module writes one JSON line per completed run, so `/usage` can answer what
a session, a day or a week consumed without asking a provider anything.

The record holds numbers only: no prompt text, no tool arguments, no file
content. Tool *names* are the one non-numeric field — they say which tool ran,
never what it was given. That is what lets it be written by default instead of
behind an opt-in.
"""

from __future__ import annotations

import dataclasses
import json
import os
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, TypeVar, cast

from zrb.config.config import CFG
from zrb.llm.shared.agent_state import get_current_ui
from zrb.llm.shared.feature_config import get_session_ui
from zrb.util.string.name import get_conversation_key

if TYPE_CHECKING:
    from zrb.llm.agent.types import RunUsage

_Record = TypeVar("_Record", bound="UsageRecord")
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
# A tool return that did not succeed: it raised, or asked the model to retry.
_FAILED_OUTCOMES = ("failed", "retried")
# Record field -> `RunUsage` attribute, where the two names differ.
_USAGE_ATTR = {"reasoning_tokens": "output_reasoning_tokens"}
# What kind of work a line accounts for. A record of an unknown kind still counts
# as a turn: a reader that drops what it does not recognise would lose tokens the
# user paid for, which is worse than filing them one section too wide.
KIND_TURN = "turn"
"""One agent round: what a conversation's turn consumed."""
KIND_SUMMARIZATION = "summarization"
"""One compaction: what replacing a history with a summary consumed."""

# Which model call a line belongs to. `kind` says *when* the work happened and
# this says *who* spent the tokens; a compaction is both, a hook's review is
# neither. The vocabulary is deliberately short: a component earns a name when a
# reader would act differently on seeing it in `/usage`, not because it is a
# distinct module. `COMPONENT_OTHER` is the honest name for a call site nobody
# has tagged yet — never drop such a line, which would lose tokens the user paid
# for.
COMPONENT_MAIN = "main_agent"
"""The conversation's own rounds."""
COMPONENT_SUMMARIZER = "summarizer"
"""One compaction, whole."""
COMPONENT_HOOK = "hook_agent"
"""An AGENT-type hook: the memory reviewer, the self-review gate, the week note."""
COMPONENT_AUTO_NAMER = "auto_namer"
"""The topic slug a conversation gets after its first message."""
COMPONENT_SHELL_JUDGE = "shell_judge"
"""The approval judge (ADR-0141)."""
COMPONENT_SUBAGENT = "subagent"
"""A delegated sub-agent's own rounds."""
COMPONENT_OTHER = "other"
"""A call site that is not tagged yet."""

# What every existing line was. Before this field existed only two modules wrote
# one, so a line's kind names its component without a guess: a compaction line
# was the summarizer, and everything else was the turn runner.
_LEGACY_COMPONENT = {
    KIND_SUMMARIZATION: COMPONENT_SUMMARIZER,
}

# Set while a nested run is not the conversation's own: the sub-agent that owns
# the run tags it, and every line written underneath inherits it without the
# call sites knowing who called them.
_current_component: ContextVar[str] = ContextVar(
    "usage_component", default=COMPONENT_MAIN
)


@contextmanager
def usage_component(component: str) -> Iterator[None]:
    """Attribute every line written inside this block to *component*."""
    token = _current_component.set(component)
    try:
        yield
    finally:
        _current_component.reset(token)


def current_component() -> str:
    """The component a line written right now belongs to."""
    return _current_component.get()


def current_conversation_name() -> str:
    """The conversation a line written right now belongs to, or "".

    The session's own UI is the authority, because it is the one the user sees
    and it is bound for the whole conversation (`_bound_session_ui`), so a
    compaction, a judge, a hook and a namer all read the same name. A run's UI
    is the fallback for a headless task that was handed one.

    A name here is not the identity: `UsageRecord.session_key` strips the slug a
    rename appends, so a name read before a rename still files the line in the
    same conversation.
    """
    for ui in (get_session_ui(), get_current_ui()):
        session = getattr(ui, "session", None)
        name = getattr(session, "conversation_session_name", "")
        if name:
            return str(name)
    return ""


# Why a compaction ran, as its record spells it. `LIMIT_TOKEN` and
# `LIMIT_MESSAGE` can appear together: a history can cross both checks at once.
COMPACTION_FORCED = "forced"
"""A person asked for it (`/compress`); no limit was reached."""
LIMIT_TOKEN = "token"
LIMIT_MESSAGE = "message"
LIMIT_BOTH = "token and message"


def record_to_dict(record: "UsageRecord") -> dict[str, object]:
    """Serialize a log record, keeping its timestamp readable."""
    raw = dataclasses.asdict(record)
    raw["timestamp"] = record.timestamp.isoformat()
    return raw


@dataclass(frozen=True)
class CompactionDetail:
    """What a compaction saw when it fired, and why it fired at all.

    Carried on the compaction's own record, because `/usage` can already say
    what a compaction cost and nothing says why it ran: the trigger is the
    configured threshold *less the system prompt*, the window can fire on
    message count alone, and `/compress` fires on neither. A reader with the
    cost and not the reason is looking at half a decision.

    `allowed_tokens` is the effective allowance the history was measured
    against: the configured trigger less `prompt_tokens`, floored at one, so a
    system prompt that outgrows the trigger leaves a one-token allowance rather
    than a negative one — in that case the pair does not add back up to the
    configured trigger. A forced compaction answers no limit, so its three token
    fields are zero and the renderer prints them as unknown rather than as
    nothing.
    """

    reason: str
    history_tokens: int
    allowed_tokens: int
    prompt_tokens: int
    messages: int
    window: int

    @classmethod
    def forced(cls, messages: int, window: int | None = None) -> "CompactionDetail":
        """A compaction a person asked for, which answers no limit.

        The token fields stay zero: nothing was measured, and the renderer says
        `forced` rather than printing zeroes as a history that measured nothing.
        *window* defaults to the configured one — the window such a history would
        have been measured against had the trigger decided.
        """
        return cls(
            reason=COMPACTION_FORCED,
            history_tokens=0,
            allowed_tokens=0,
            prompt_tokens=0,
            messages=messages,
            window=CFG.LLM_HISTORY_SUMMARIZATION_WINDOW if window is None else window,
        )


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
    # Which model call spent these tokens. A line written before this field
    # existed reads back by its kind, which names it without a guess.
    component: str = COMPONENT_MAIN
    # Calls and failures per tool name. A line without them reads back as empty.
    tool_counts: dict[str, int] = field(default_factory=dict)
    tool_errors: dict[str, int] = field(default_factory=dict)
    # Why a compaction ran. Absent on a turn, and on every line written before
    # this field existed.
    compaction: CompactionDetail | None = None

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
        return record_to_dict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> UsageRecord:
        """Rebuild a record; raises when *raw* is not one."""
        counts = {name: _as_int(raw, name) for name in _INT_FIELDS}
        kind = str(raw["kind"])
        return cls(
            timestamp=as_datetime(raw["timestamp"]),
            model=str(raw["model"]),
            session=str(raw["session"]),
            kind=kind,
            duration_ms=_as_int(raw, "duration_ms"),
            cost=_as_cost(raw.get("cost")),
            component=str(raw.get("component") or _LEGACY_COMPONENT.get(kind, COMPONENT_MAIN)),
            tool_counts=_as_name_counts(raw.get("tool_counts")),
            tool_errors=_as_name_counts(raw.get("tool_errors")),
            compaction=_as_compaction(raw.get("compaction")),
            **counts,
        )


def usage_store_path(when: datetime, directory: str | None = None) -> str:
    """The month file a record at *when* belongs to.

    One file per month, so a week's question reads one file and a month's reads
    one — rather than one growing file that every query has to scan whole.
    """
    return store_path(_FILE_PREFIX, when, directory)


def store_path(prefix: str, when: datetime, directory: str | None = None) -> str:
    """The month file of the log named by *prefix* that *when* belongs to."""
    base = directory if directory is not None else CFG.LLM_USAGE_DIR
    return os.path.join(base, f"{prefix}{when.strftime(_MONTH_FORMAT)}{_FILE_SUFFIX}")


class UsageTotals:
    """Counts added up over several model calls, and the cost that came with them.

    A compaction is one charge made of a handful of calls — one per chunk, the
    consolidation when there are several, a shortening attempt when the snapshot
    runs long — and `/usage` reports the event, so the calls are added here
    before a line is written. `cost` stays ``None`` until a call reports one: an
    unpriced total is unknown, never free.

    Mutable on purpose. The calls happen at the leaves of the summarizer's call
    tree, and handing a return value back up through every level would change
    six signatures to carry one number.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    requests: int = 0
    tool_calls: int = 0
    unmeasured_requests: int = 0
    cost: float | None = None
    model: str = ""

    def add(self, usage: RunUsage, model: str = "") -> None:
        """Fold one call's numbers in."""
        for name in _INT_FIELDS:
            setattr(
                self,
                name,
                getattr(self, name) + _count_of(usage, _USAGE_ATTR.get(name, name)),
            )
        cost = _cost_of(usage)
        if cost is not None:
            self.cost = cost if self.cost is None else self.cost + cost
        if model:
            self.model = model


def record_usage(
    usage: RunUsage,
    *,
    model: str,
    session: str = "",
    kind: str = KIND_TURN,
    duration_ms: int = 0,
    when: datetime | None = None,
    tool_counts: dict[str, int] | None = None,
    tool_errors: dict[str, int] | None = None,
    component: str | None = None,
) -> UsageRecord | None:
    """Append one run to the log.

    *component* names what spent the tokens; left out, it is whatever
    `usage_component` set around the call, and `main_agent` outside one.
    *session* left empty is the ambient conversation's — see `record_totals`.

    Returns the record that was written, or ``None`` when the log could not be
    written — a full disk or a read-only home must not fail the turn that
    produced the numbers.
    """
    totals = UsageTotals()
    totals.add(usage, model=model)
    return record_totals(
        totals,
        session=session,
        kind=kind,
        duration_ms=duration_ms,
        when=when,
        tool_counts=tool_counts,
        tool_errors=tool_errors,
        component=component,
    )


def record_totals(
    totals: UsageTotals,
    *,
    session: str = "",
    kind: str = KIND_TURN,
    duration_ms: int = 0,
    when: datetime | None = None,
    tool_counts: dict[str, int] | None = None,
    tool_errors: dict[str, int] | None = None,
    compaction: CompactionDetail | None = None,
    component: str | None = None,
) -> UsageRecord | None:
    """Append one line for *totals*, under the same contract as `record_usage`."""
    if _is_empty(totals):
        return None
    if not session:
        # An auxiliary call — the judge, a hook, the namer, a side question —
        # runs inside a conversation and is never handed its name. Without
        # this its tokens land in `today` and never in `/usage session`, which
        # is the window the new section is read in. `session_key` strips the
        # slug a rename appends, so an older name still names the same
        # conversation.
        session = current_conversation_name()
    record = UsageRecord(
        timestamp=when if when is not None else datetime.now(timezone.utc),
        model=totals.model,
        session=session,
        kind=kind,
        duration_ms=duration_ms,
        cost=totals.cost,
        component=component if component is not None else current_component(),
        tool_counts=dict(tool_counts or {}),
        tool_errors=dict(tool_errors or {}),
        compaction=compaction,
        **{name: getattr(totals, name) for name in _INT_FIELDS},
    )
    return _write_record(record)


def record_agent_usage(
    result: object,
    *,
    component: str,
    model: str = "",
    session: str = "",
    duration_ms: int = 0,
    when: datetime | None = None,
) -> UsageRecord | None:
    """Write one line for a finished `agent.run(...)`, under *component*.

    Every auxiliary model call zrb makes has a `RunResult` in hand when it
    finishes and no line in the log, because the only writer was the turn
    runner. This is that writer for them: it takes the result, so a call site
    does not have to know whether usage is a method or an attribute on the
    object its agent returns, and it writes through `record_usage`, so an empty
    run still writes nothing.

    *session* left empty is the conversation the call ran inside: an auxiliary
    call is never handed a name, and a judge's tokens should count toward the
    session whose command it judged.
    """
    usage = getattr(result, "usage", None)
    if callable(usage):
        usage = usage()
    if usage is None:
        return None
    if not model:
        # The agent answers with the model it actually used, which is more than
        # a call site knows: the request may have been routed or defaulted.
        model = str(getattr(getattr(result, "response", None), "model_name", "") or "")
    return record_usage(
        cast("RunUsage", usage),
        model=model,
        session=session,
        duration_ms=duration_ms,
        component=component,
        when=when,
    )


def _write_record(record: UsageRecord) -> UsageRecord | None:
    """Append *record* to its month file, or ``None`` when the file system refused it."""
    path = usage_store_path(record.timestamp)
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
    for path in store_files(_FILE_PREFIX, since, until, directory):
        records.extend(
            read_month_file(
                path,
                _parse_line,
                since,
                until,
                lambda record: session_key is None or record.session_key == session_key,
            )
        )
    records.sort(key=lambda record: record.timestamp)
    return records


def store_files(
    prefix: str,
    since: datetime | None,
    until: datetime | None,
    directory: str | None,
) -> list[str]:
    """The month files of the log named by *prefix* that can hold a line in the window.

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
        return _files_in(base, prefix)
    start = as_datetime(since).astimezone(timezone.utc)
    end = (
        as_datetime(until).astimezone(timezone.utc)
        if until is not None
        else datetime.now(timezone.utc)
    )
    candidates = [
        store_path(prefix, month, base) for month in _months_between(start, end)
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


def _files_in(base: str, prefix: str) -> list[str]:
    """Every file of the log named by *prefix* in *base*, in name order (which is month order)."""
    try:
        names = os.listdir(base)
    except OSError:
        return []
    return [
        os.path.join(base, name)
        for name in sorted(names)
        if name.startswith(prefix) and name.endswith(_FILE_SUFFIX)
    ]


def read_month_file(
    path: str,
    parse: Callable[[str], _Record | None],
    since: datetime | None,
    until: datetime | None,
    in_session: Callable[[_Record], bool],
) -> list[_Record]:
    """The records of one month file that *parse* accepts, that fall inside the
    window and that satisfy *in_session*.

    An unreadable file is empty and an unreadable line is skipped: a damaged log
    costs the records it cannot parse, never the whole read.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return []
    records: list[_Record] = []
    for line in lines:
        record = parse(line)
        if record is None:
            continue
        if since is not None and record.timestamp < as_datetime(since):
            continue
        if until is not None and record.timestamp > as_datetime(until):
            continue
        if not in_session(record):
            continue
        records.append(record)
    return records


def parse_line(
    line: str, from_dict: Callable[[dict[str, object]], _Record], what: str
) -> _Record | None:
    """One JSONL line as a record via *from_dict*, or ``None`` when it is not
    one. *what* names the line in the debug log."""
    text = line.strip()
    if not text:
        return None
    try:
        return from_dict(json.loads(text))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        CFG.LOGGER.debug(f"Skipping an unreadable {what}: {text[:80]}")
        return None


def _parse_line(line: str) -> UsageRecord | None:
    return parse_line(line, UsageRecord.from_dict, "usage line")


def count_tool_calls(
    messages: Iterable[object],
) -> tuple[dict[str, int], dict[str, int]]:
    """Calls and failures per tool name across a run's *messages*.

    Read off the messages the run already holds, once per round, so nothing
    runs per token or per tool call. A call is a tool-call part; a failure is a
    tool return whose outcome is `failed` or `retried` (the tool raised, the model
    sent bad arguments, or the tool asked to be retried), or the older retry
    prompt addressed to a tool. Parts are read by their `part_kind` rather than
    their class, which keeps this module free of a `pydantic_ai` import. Only
    names are kept — never arguments.
    """
    calls: dict[str, int] = {}
    errors: dict[str, int] = {}
    for message in messages:
        for part in getattr(message, "parts", None) or ():
            kind = getattr(part, "part_kind", "")
            name = getattr(part, "tool_name", None)
            if not isinstance(name, str) or not name:
                continue
            if kind == "tool-call":
                calls[name] = calls.get(name, 0) + 1
            elif kind == "retry-prompt" or (
                kind == "tool-return"
                and getattr(part, "outcome", "") in _FAILED_OUTCOMES
            ):
                errors[name] = errors.get(name, 0) + 1
    return calls, errors


def _is_empty(usage: "RunUsage | UsageTotals") -> bool:
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


def _count_of(usage: "RunUsage | UsageTotals", name: str) -> int:
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


def _as_name_counts(value: object) -> dict[str, int]:
    """A `{name: count}` map; anything else, and any bad entry, is dropped.

    These fields are optional detail, so a malformed one must not make the
    whole line — and its token counts — unreadable."""
    if not isinstance(value, dict):
        return {}
    return {
        name: int(count)
        for name, count in value.items()
        if isinstance(name, str)
        and isinstance(count, (int, float))
        and not isinstance(count, bool)
    }


def _as_compaction(value: object) -> CompactionDetail | None:
    """Why a compaction ran, or ``None`` where the line does not say.

    Optional detail, like the tool counts: a malformed one is dropped rather
    than making the record — and the tokens it cost — unreadable. Every line
    written before this field existed answers ``None``.
    """
    if not isinstance(value, dict):
        return None
    try:
        return CompactionDetail(
            reason=str(value["reason"]),
            history_tokens=int(value["history_tokens"]),
            allowed_tokens=int(value["allowed_tokens"]),
            prompt_tokens=int(value["prompt_tokens"]),
            messages=int(value["messages"]),
            window=int(value["window"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _as_cost(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        raise ValueError(f"cost is not a number: {value!r}")
    return float(value)


def as_datetime(value: object) -> datetime:
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
