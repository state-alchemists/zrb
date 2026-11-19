"""One log row per model request, so a turn's spend can be read where it was made.

`usage_log` writes one line per *round* — a turn's requests summed into a single
number — and that is the right line for a bill. It cannot say why the round cost
what it did: a round of fifty-four requests is one line, and whether the input
rose because the history grew, because a tool returned something enormous, or
because zrb resent a prefix it had rewritten is invisible at that size (board
0003 §4).

So this module writes a second file beside the first, `request-YYYY-MM.jsonl`,
one line per model request. Two fields carry what the sum cannot:

`reason` says what the request is in its turn — the opening of the turn, a
follow-up after a tool returned, a resend after a stream error, a round that
resumes a deferred approval, or a round an extension kept going.

`prompt_hash` is a digest of the messages as sent, and it settles the
zero-cache read mid-session (§7.7). Two requests with the same digest and a
different cache read sent the same prompt and were answered differently, which
is the provider's doing; a digest that changes while `prompt_messages` stays
put says zrb rewrote the prefix in place, which is zrb's.

The two logs join on `turn`, the id `TurnCursor.turn_id` gives every round of
one turn and `UsageRecord.turn` carries onto the summed line.

Only numbers, a reason and a digest are written — never prompt text. The digest
covers what the provider was sent: the messages' parts and the request's
instructions, since a prompt whose instructions changed is a prompt the cache
cannot match. Bookkeeping it does not receive is stripped first — part and
message timestamps, the metadata zrb hangs on a message, provider details,
response ids, and what a response cost — because a retry rebuilds those, and a
digest that folded them in would report every resend as a changed prompt. Tool
definitions are left out entirely: they are not part of the message list, and
they are constant per configuration and priced separately (ADR-0058).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast

from zrb.config.config import CFG
from zrb.llm.contracts.shared.usage_log import (
    current_component,
    current_conversation_name,
    is_within_window,
    parse_line,
    read_month_file,
    store_files,
    store_path,
)
from zrb.util.string.name import get_conversation_key

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage

    from zrb.llm.engine.agent.run.turn_cursor import TurnCursor
    from zrb.llm.engine.agent.run.typing_aliases import History

_FILE_PREFIX = "request-"
_FILE_SUFFIX = ".jsonl"
_MONTH_FORMAT = "%Y-%m"
# How much of the digest a line keeps. Twelve hex characters name a prompt
# within a conversation as well as the whole digest would, and a reader can
# compare two rows by eye.
_DIGEST_CHARS = 12
# Bookkeeping the provider never receives: part and call ids, timestamps, the
# provider's own identifiers, and the metadata zrb hangs on a message. A retry
# rebuilds most of these — a `UserPromptPart` is stamped when it is made — so a
# digest that folded them in would report a changed prompt whenever the same
# prompt was sent twice, which is the one comparison the digest exists to make.
_UNSENT_KEYS = frozenset(
    {
        "timestamp",
        "id",
        "run_id",
        "conversation_id",
        "metadata",
        "provider_details",
        "provider_name",
        "provider_url",
        "provider_response_id",
        "history_digest",
        "failed_attempts",
        "state",
        # What a response cost and which model answered it. Not sent back to the
        # model: the next request carries the answer's parts and nothing else.
        "usage",
        "model_name",
        "model_id",
        "finish_reason",
        "canonical_system",
        "workspace_ref",
    }
)
# Record field -> `RequestUsage` attribute, where the two names differ.
_COUNT_ATTR = {
    "input_tokens": "input_tokens",
    "output_tokens": "output_tokens",
    "cache_read_tokens": "cache_read_tokens",
    "cache_write_tokens": "cache_write_tokens",
    "reasoning_tokens": "output_reasoning_tokens",
}

# Why a request was sent. The opening request of a turn carries what opened the
# round it sits in; every later request of that round is a follow-up, because
# the only thing that can put another request inside a round is a tool return.
REASON_OPENING = "opening"
"""The first request of a turn: the one the prepared history was sent in."""
REASON_FOLLOW_UP = "follow_up"
"""A later request in the same round, sent after a tool returned."""
REASON_RETRY = "retry"
"""A round re-sent after a stream error or an empty completion."""
REASON_RESUME = "resume"
"""A round that continues the turn after a deferred approval."""
REASON_CONTINUE = "continue"
"""A round an extension kept going after the turn had answered."""
# The call sites that run an agent themselves and never enter the turn loop.
# Their spend is one summed line in `usage_log`, which answers the bill and
# cannot say which of them spent it; a reason on the row is what says it. These
# are named after the site, not after the component, because the components
# overlap — a hook, the judge and the namer all run under a name of their own
# only sometimes.
REASON_HOOK = "hook"
"""One of the hooks `hook_agent.py` builds as a real sub-agent turn.

Four of them call a model — memory recall, memory review, self review, the
weekly write — and they share this reason: all four spend under the same
component too. Splitting it is step 2 of board 0003 §4, and it needs the hook
read before the name is worth splitting.
"""
REASON_MEMORY_WEEK = "memory_week"
"""The weekly diary write, which runs on a schedule rather than in a turn."""
REASON_SHELL_JUDGE = "shell_judge"
"""The judge that reads a shell command before the run is allowed to send it."""
REASON_NAMER = "namer"
"""The suggestion for a conversation's name, asked on the opening turn."""
REASON_SUMMARIZER = "summarizer"
"""A conversation, or a day of one, read down to a summary."""
REASON_SIDE_QUESTION = "side_question"
"""A question asked beside the conversation instead of as a turn of it."""
REASON_DICTATION_JUDGE = "dictation_judge"
"""The judge that decides whether spoken words interrupt the run."""
REASON_SPEECH = "speech"
"""An answer's text read down to the part worth saying out loud."""
REASON_PLEASE = "please"
"""`zrb llm please`: a sentence read into one command line."""
REASON_CHANGELOG = "changelog"
"""A changelog draft, written from the commits since the previous tag."""


@dataclass(frozen=True)
class RequestRecord:
    """One model request, as it is written to the request log."""

    timestamp: datetime
    model: str
    session: str
    # Which call site spent these tokens, in the vocabulary `usage_log` defines.
    component: str
    reason: str
    # The turn this request belongs to, and its position inside it. Both the
    # turn's summed line and every request under it carry the same `turn`.
    turn: str
    index: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int
    # How many messages the prompt carried, and the digest of what they said.
    prompt_messages: int
    prompt_hash: str
    cost: float | None = None

    @property
    def session_key(self) -> str:
        """The conversation this request belongs to, stable across a rename.

        The same identity `UsageRecord.session_key` uses, so a request row and
        the turn it belongs to answer to one conversation key.
        """
        return get_conversation_key(self.session)

    def to_dict(self) -> dict[str, object]:
        """Serialize the row, keeping its timestamp readable."""
        raw = dataclasses.asdict(self)
        raw["timestamp"] = self.timestamp.isoformat()
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> "RequestRecord":
        """Rebuild a row; raises when *raw* is not one."""
        return cls(
            timestamp=_as_datetime(raw["timestamp"]),
            model=str(raw["model"]),
            session=str(raw["session"]),
            component=str(raw["component"]),
            reason=str(raw["reason"]),
            turn=str(raw["turn"]),
            index=_as_int(raw, "index"),
            prompt_messages=_as_int(raw, "prompt_messages"),
            prompt_hash=str(raw["prompt_hash"]),
            cost=_as_cost(raw.get("cost")),
            **{name: _as_int(raw, name) for name in _COUNT_ATTR},
        )


def requests_store_path(when: datetime, directory: str | None = None) -> str:
    """The month file a request row at *when* belongs to."""
    return store_path(_FILE_PREFIX, when, directory)


def record_round_requests(
    cursor: "TurnCursor", new_messages: History, reason: str
) -> None:
    """Write a row for every request the round that just finished sent.

    *reason* names what opened the round; the round's later requests are filed
    as follow-ups. The cursor's own counter carries on across rounds, so a turn's
    rows are numbered `0, 1, 2…` even when a round is retried.

    *new_messages* are the messages the run produced. A result that cannot give
    them — a mocked run, a provider that raised — writes no row rather than a
    guessed one, which is why the list is checked rather than trusted.
    """
    if not isinstance(new_messages, list):
        return
    rows = _rows_for(
        history=cursor.history,
        new_messages=new_messages,
        turn=cursor.turn_id,
        first_index=cursor.requests,
        reason=reason,
    )
    cursor.requests += len(rows)
    record_requests(rows)


def record_standalone_requests(
    result: object,
    reason: str,
    *,
    component: str,
    history: History | None = None,
) -> list[RequestRecord]:
    """Write a row for every request a run outside the turn loop sent.

    The auxiliary call sites — the hooks, the shell judge, the namer, the
    summarizer, a side question, dictation's judge, speech — run an agent
    themselves and never enter the turn loop, so `record_round_requests` never
    sees them. Each of them writes one summed line through `record_agent_usage`,
    which answers the bill and cannot say which of them spent it; these rows say
    that, and carry the digest that says whether the prompt was paid again.

    *reason* names the call site. Such a run has no turn of its own, so one is
    minted here: a call's rows join on it, and it joins nothing else. A later
    request inside the same run is filed as a follow-up, the same way a round's
    are.

    *component* is the name the site also gives `record_agent_usage`, and it is
    required because these calls run *beside* a turn rather than inside it: the
    ambient component is whatever the turn set, so reading it here would file a
    hook's tokens under the main agent and leave the request row disagreeing
    with the summed line it is meant to explain. Both writers are handed the
    same constant, which is the one way the two cannot drift.

    *history* is what the run was handed as `message_history`, when it was
    handed one: a side question reads the conversation so far and sends it with
    the question, so a row that folded an empty history would report a prompt of
    one message for a prompt that carried the conversation. Only the run's own
    requests get rows — the history is folded into the count and the digest
    without being yielded, the way a turn's earlier rounds are.

    A result that cannot give its messages writes no rows rather than a guessed
    one, the same rule the turn's writer follows.
    """
    messages = _messages_of(result)
    if not messages:
        return []
    return record_requests(
        _rows_for(
            history=history if history is not None else [],
            new_messages=messages,
            turn=uuid.uuid4().hex,
            first_index=0,
            reason=reason,
            component=component,
        )
    )


def _messages_of(result: object) -> History:
    """The messages a finished run produced, or nothing when it cannot say."""
    new_messages = getattr(result, "new_messages", None)
    if not callable(new_messages):
        return []
    produced = new_messages()
    return produced if isinstance(produced, list) else []


def _rows_for(
    *,
    history: History,
    new_messages: History,
    turn: str,
    first_index: int,
    reason: str,
    component: str | None = None,
) -> list[RequestRecord]:
    """The rows one run's requests make, numbered from *first_index*.

    Shared by the turn's writer and the standalone one so the two cannot drift
    on what a row says; the only difference between them is where the turn id,
    the starting index and the component come from. *component* left out is the
    ambient one, which is right for a round: the turn loop binds it, so a
    round's rows are filed under the component that ran it.
    """
    session = current_conversation_name()
    row_component = current_component() if component is None else component
    rows: list[RequestRecord] = []
    index = first_index
    for digest, prompt_messages, response in _requests_sent(history, new_messages):
        rows.append(
            RequestRecord(
                timestamp=_stamp(response),
                model=_model_of(response),
                session=session,
                component=row_component,
                reason=reason if index == first_index else REASON_FOLLOW_UP,
                turn=turn,
                index=index,
                prompt_hash=digest,
                prompt_messages=prompt_messages,
                cost=_cost_of(response),
                **counts_of_request(getattr(response, "usage", None)),
            )
        )
        index += 1
    return rows


def record_requests(records: Iterable[RequestRecord]) -> list[RequestRecord]:
    """Append every row to its month file; returns the rows that were written.

    One file is opened per month rather than per row, since a round's requests
    are milliseconds apart and a turn's are minutes apart. A log that cannot be
    written costs its rows and never the turn that produced them.
    """
    written: list[RequestRecord] = []
    for path, rows in _by_month_file(records):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")
        except OSError:
            CFG.LOGGER.debug(f"Request log not written: {path}", exc_info=True)
            continue
        written.extend(rows)
    return written


def read_requests(
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    session_key: str | None = None,
    directory: str | None = None,
) -> list[RequestRecord]:
    """Every request row in the window, oldest first.

    *session_key* selects one conversation by its stable key, so a conversation
    renamed after its first turn still answers for that turn. An unreadable line
    is skipped, like the summed log: one corrupt byte must not make the history
    unreadable.
    """
    rows: list[RequestRecord] = []
    for path in store_files(_FILE_PREFIX, since, until, directory):
        rows.extend(
            read_month_file(
                path,
                _parse_line,
                lambda row: is_within_window(row.timestamp, since, until)
                and (session_key is None or row.session_key == session_key),
            )
        )
    rows.sort(key=lambda row: row.timestamp)
    return rows


def counts_of_request(usage: object) -> dict[str, int]:
    """The five token fields of one request's usage, as plain integers."""
    return {
        name: _as_count(getattr(usage, attr, 0))
        for name, attr in _COUNT_ATTR.items()
    }


def _requests_sent(
    base: History, new_messages: History
) -> Iterator[tuple[str, int, object]]:
    """Each request the round sent: its prompt's digest, its length, its response.

    The digest is folded forward one message at a time, so the prompt of the
    fourth request costs the fourth message and not the thousand before it. The
    base is folded first and never yielded: those are requests an earlier round
    already filed, and the round that made them has its own rows.
    """
    hasher = hashlib.sha256()

    def fold(messages: History, count: int) -> int:
        for message in messages:
            hasher.update(_fingerprint(message))
            count += 1
        return count

    count = fold(base, 0)
    for message in new_messages:
        if getattr(message, "kind", None) == "response":
            yield hasher.hexdigest()[:_DIGEST_CHARS], count, message
        count = fold([message], count)


def _fingerprint(message: "ModelMessage") -> bytes:
    """What the provider was sent of *message*, canonicalized for hashing.

    The message is serialized the way pydantic-ai would send it and then stripped
    of the fields no provider receives (`_UNSENT_KEYS`). Both halves matter: the
    serialization is the framework's own idea of what a message is, and the strip
    is what makes two sendings of one prompt hash alike. A retry rebuilds the
    request message and stamps a new `UserPromptPart`, so without the strip the
    same prompt would read as a changed one — the wrong answer to the question
    this digest exists to answer.
    """
    # lazy: heavy third-party
    from pydantic_ai.messages import ModelMessagesTypeAdapter

    (raw,) = json.loads(ModelMessagesTypeAdapter.dump_json([message]))
    return json.dumps(
        _without_unsent(raw), sort_keys=True, ensure_ascii=False
    ).encode("utf-8")


def _without_unsent(value: object) -> object:
    """*value* with every bookkeeping key removed, at any depth."""
    if isinstance(value, dict):
        return {
            key: _without_unsent(item)
            for key, item in value.items()
            if key not in _UNSENT_KEYS
        }
    if isinstance(value, list):
        return [_without_unsent(item) for item in value]
    return value


def _by_month_file(
    records: Iterable[RequestRecord],
) -> Iterator[tuple[str, list[RequestRecord]]]:
    """The rows grouped by the month file each belongs to, in first-seen order."""
    grouped: dict[str, list[RequestRecord]] = {}
    for record in records:
        grouped.setdefault(requests_store_path(record.timestamp), []).append(record)
    yield from grouped.items()


def _parse_line(line: str) -> RequestRecord | None:
    return parse_line(line, RequestRecord.from_dict, "request line")


def _stamp(response: object) -> datetime:
    """When the response finished, which is the request's own timestamp."""
    value = getattr(response, "timestamp", None)
    return value if isinstance(value, datetime) else datetime.now(timezone.utc)


def _model_of(response: object) -> str:
    """The model that answered, which may differ from the one asked for."""
    value = getattr(response, "model_name", None)
    return value if isinstance(value, str) else ""


def _cost_of(response: object) -> float | None:
    """The request's cost when the provider priced it; ``None`` is not zero."""
    value = getattr(getattr(response, "usage", None), "cost", None)
    if value is None:
        return None
    try:
        return float(cast(float, value))
    except (TypeError, ValueError):
        return None


def _as_count(value: object) -> int:
    return int(cast(int, value)) if isinstance(value, (int, float)) else 0


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
    """A timezone-aware datetime; a naive one is read as UTC, like the summed log."""
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
