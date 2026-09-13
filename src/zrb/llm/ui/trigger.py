"""The item vocabulary a chat trigger yields.

A trigger is a callable returning an async iterable; every item it yields
becomes a user turn. Yielding a plain string sends text alone; yielding a
`TriggerMessage` — or any `(text, attachments)` two-tuple — sends text together
with attachments, so an external source can hand the agent a photo, a PDF or a
file path the way `/photo` and `/attach` do.

`attachments` must be a sequence; `None` reads as none, matching the default
below. A tuple of any other length, or a bare string where the sequence
belongs, is reported against that item and the trigger carries on with the
next one.
"""

from __future__ import annotations

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
