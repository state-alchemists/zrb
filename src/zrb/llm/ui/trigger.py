"""The item vocabulary a chat trigger yields.

A trigger is a callable returning an async iterable; every item it yields
becomes a user turn. Yielding a plain string sends text alone; yielding a
`TriggerMessage` — or any `(text, attachments)` two-tuple — sends text together
with attachments, so an external source can hand the agent a photo, a PDF or a
file path the way `/photo` and `/attach` do. Yielding a `TriggerReply` answers
the tool approval or question the user is being asked, if there is one.

A malformed item is reported and the trigger carries on with the next one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NamedTuple

from zrb.llm.input_source import InputProvenance

if TYPE_CHECKING:
    from zrb.llm.agent.types import UserContent


class TriggerMessage(NamedTuple):
    """A trigger item carrying attachments alongside its text.

    `attachments` accepts whatever `/attach` accepts: a file path or a
    `BinaryContent`. An item with neither text nor attachments is skipped.
    """

    text: str = ""
    attachments: "Sequence[UserContent]" = ()


@dataclass(frozen=True)
class TriggerInput:
    """A trigger message with attachments and input provenance."""

    text: str = ""
    attachments: "Sequence[UserContent]" = ()
    source: InputProvenance | None = None


@dataclass(frozen=True)
class TriggerReply:
    """A trigger item that answers the pending approval or question.

    `text` is what the user said. It answers a question, and with nothing
    pending it becomes a user turn like a plain string. `approval` is what to
    send instead when the pending prompt is a tool approval, which reads
    ``y``/``yes`` as approve and anything else as a denial; ``None`` sends
    `text`. An empty answer is never sent: it would approve.

    `started_at` is `time.monotonic()` when the user began speaking. When set,
    the reply answers only a prompt that was already pending by then; a prompt
    that appeared later gets `text` as a user turn instead, so a "yes" said to
    nothing cannot approve a tool call shown while it was being transcribed.

    Only a trigger that speaks for the user (dictation) should yield one: a
    scheduled or remote source must not be able to approve a tool call.
    """

    text: str
    approval: str | None = None
    started_at: float | None = None
    source: InputProvenance | None = field(default=None, init=False, compare=False)
