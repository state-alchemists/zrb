"""The item vocabulary a chat trigger yields.

A trigger is a callable returning an async iterable; every item it yields
becomes a user turn. Yielding a plain string sends text alone; yielding a
`TriggerMessage` — or any `(text, attachments)` two-tuple — sends text together
with attachments, so an external source can hand the agent a photo, a PDF or a
file path the way `/photo` and `/attach` do. Yielding a `TriggerReply` answers
the tool approval or question the user is being asked, if there is one.

`attachments` must be a sequence; `None` reads as none, matching the default
below. A tuple of any other length, or a bare string where the sequence
belongs, is reported against that item and the trigger carries on with the
next one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple, Sequence

if TYPE_CHECKING:
    from zrb.llm.agent.types import UserContent


class TriggerMessage(NamedTuple):
    """A trigger item carrying attachments alongside its text.

    `attachments` accepts whatever `/attach` accepts: a file path — resolved,
    size-checked, PDF-extracted and image-scaled when the turn is submitted —
    or an already-built `BinaryContent`. An item with neither text nor
    attachments is skipped, so a trigger can yield `TriggerMessage()` for
    "nothing happened".
    """

    text: str = ""
    attachments: "Sequence[UserContent]" = ()


@dataclass(frozen=True)
class TriggerReply:
    """A trigger item that answers the pending approval or question.

    The text is the answer as if the user had typed it: an approval reads
    ``y``/``yes`` as approve and anything else as a denial. With nothing
    pending it becomes a user turn like a plain string. Only a trigger that
    speaks for the user (dictation) should yield one: a scheduled or remote
    source must not be able to approve a tool call.
    """

    text: str
