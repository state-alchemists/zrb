"""Taking the emotion emoji out of the model's reply, wherever the reply goes.

The model opens its reply with an emoji for how it feels (`emotion_live`).
`ReplyEmotion` is a pydantic-ai capability that removes it from both copies
of the reply: the streamed events every UI, speech and observer read
(`wrap_run_event_stream`), and the finished response the output, history and
hooks are made from (`after_model_request`). The emotion is kept as state
instead (`current_reply_emotion`), so the user never sees the emoji.

Imported only when a run builds the capability: it loads pydantic-ai.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from dataclasses import replace

from pydantic_ai import RunContext
from pydantic_ai.capabilities.abstract import AbstractCapability
from pydantic_ai.messages import (
    AgentStreamEvent,
    ModelResponse,
    ModelResponsePart,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)
from pydantic_ai.models import ModelRequestContext

from zrb.llm.ambient_state import current_reply_emotion
from zrb.llm.emotion.label import get_leading_emotion


class ReplyEmotion(AbstractCapability[None]):
    """Remove the emotion emoji a reply opens with, set `current_reply_emotion`
    to it, and pass each emotion read to *on_emotion*. *on_stream_start* runs
    before a streamed response's first event."""

    def __init__(
        self,
        on_emotion: Callable[[str], Awaitable[None]],
        on_stream_start: Callable[[], Awaitable[None]],
    ) -> None:
        self._on_emotion = on_emotion
        self._on_stream_start = on_stream_start

    async def wrap_run_event_stream(
        self,
        ctx: RunContext[None],
        *,
        stream: AsyncIterable[AgentStreamEvent],
    ) -> AsyncIterator[AgentStreamEvent]:
        await self._on_stream_start()
        opening = _Opening()
        async for event in stream:
            for out in opening.take(event):
                if isinstance(out, str):
                    await self._read(out)
                else:
                    yield out
        for out in opening.flush():
            if not isinstance(out, str):
                yield out

    async def after_model_request(
        self,
        ctx: RunContext[None],
        *,
        request_context: ModelRequestContext,
        response: ModelResponse,
    ) -> ModelResponse:
        # Only the first non-blank text part can carry the emoji.
        index = next(
            (
                i
                for i, part in enumerate(response.parts)
                if isinstance(part, TextPart) and part.content.strip()
            ),
            None,
        )
        # The emotion itself was read from the stream, which this
        # capability makes every run produce.
        if index is None or not _part_emotion(response.parts[index]):
            return response
        parts = list(response.parts)
        parts[index] = _strip_part(parts[index])
        return replace(response, parts=parts)

    async def _read(self, emotion: str) -> None:
        current_reply_emotion.set(emotion)
        if emotion:
            await self._on_emotion(emotion)


class _Opening:
    """Buffers a response's events from the start of its first text part
    until that part has visible text, then releases them in order with the
    leading emoji removed. Later text parts pass through untouched.

    `take` and `flush` return the events to pass on. A `str` among them is
    the emotion read, ``""`` when the reply opens without one."""

    def __init__(self) -> None:
        self._held: list[AgentStreamEvent] = []
        self._index: int | None = None
        self._text = ""
        # Indexes of parts whose emoji was removed, so their end event is
        # stripped too.
        self._stripped: set[int] = set()
        # Index of a part whose text so far is only the emoji and blanks;
        # the blanks that follow are dropped until its text starts.
        self._trimming: int | None = None
        # True once visible text has been seen; later parts pass untouched.
        self._is_opening_read = False

    def take(self, event: AgentStreamEvent) -> "list[AgentStreamEvent | str]":
        if (
            isinstance(event, PartStartEvent)
            and isinstance(event.part, TextPart)
            and not self._is_opening_read
        ):
            self._trimming = None
            passed = self.flush()
            self._held = [event]
            self._index = event.index
            self._text = event.part.content
            return passed + self._release_if_visible()
        if self._index is None:
            return self._trim(self._clean_end(event))
        if isinstance(event, PartEndEvent) and event.index == self._index:
            return self.flush() + [event]
        self._held.append(event)
        if _is_text_delta(event, self._index):
            assert isinstance(event, PartDeltaEvent)
            assert isinstance(event.delta, TextPartDelta)
            self._text += event.delta.content_delta
            return self._release_if_visible()
        return []

    def flush(self) -> "list[AgentStreamEvent | str]":
        """Release the held events unchanged; their part had no visible
        text."""
        held, self._held, self._index, self._text = self._held, [], None, ""
        return list(held)

    def _release_if_visible(self) -> "list[AgentStreamEvent | str]":
        if not self._text.strip():
            return []
        emotion = get_leading_emotion(self._text) or ""
        cut = len(self._text) - len(_strip_text(self._text)) if emotion else 0
        index, held, text = self._index, self._held, self._text
        self._held, self._index, self._text = [], None, ""
        self._is_opening_read = True
        if cut:
            assert index is not None
            self._stripped.add(index)
            held = _cut_text(held, index, cut)
            if not _strip_text(text):
                self._trimming = index
        return [emotion, *held]

    def _trim(self, event: AgentStreamEvent) -> "list[AgentStreamEvent | str]":
        """Drop the whitespace after an emoji that arrived in a delta of its
        own, until the part's text starts."""
        if self._trimming is None or not _is_text_delta(event, self._trimming):
            return [event]
        assert isinstance(event, PartDeltaEvent)
        assert isinstance(event.delta, TextPartDelta)
        content = event.delta.content_delta.lstrip()
        if not content:
            return []
        self._trimming = None
        return [replace(event, delta=replace(event.delta, content_delta=content))]

    def _clean_end(self, event: AgentStreamEvent) -> AgentStreamEvent:
        if isinstance(event, PartEndEvent) and event.index in self._stripped:
            return replace(event, part=_strip_part(event.part))
        return event


def _cut_text(
    events: list[AgentStreamEvent], index: int, cut: int
) -> list[AgentStreamEvent]:
    """*events* with the first *cut* characters of part *index*'s text gone,
    dropping a delta left empty."""
    kept: list[AgentStreamEvent] = []
    for event in events:
        if (
            cut
            and isinstance(event, PartStartEvent)
            and isinstance(event.part, TextPart)
        ):
            content = event.part.content
            event = replace(event, part=replace(event.part, content=content[cut:]))
            cut -= min(cut, len(content))
        elif cut and _is_text_delta(event, index):
            assert isinstance(event, PartDeltaEvent)
            assert isinstance(event.delta, TextPartDelta)
            content = event.delta.content_delta
            cut, content = cut - min(cut, len(content)), content[cut:]
            if not content:
                continue
            event = replace(event, delta=replace(event.delta, content_delta=content))
        kept.append(event)
    return kept


def _is_text_delta(event: AgentStreamEvent, index: int) -> bool:
    return (
        isinstance(event, PartDeltaEvent)
        and isinstance(event.delta, TextPartDelta)
        and event.index == index
    )


def _part_emotion(part: ModelResponsePart) -> str:
    return get_leading_emotion(part.content) or "" if isinstance(part, TextPart) else ""


def _strip_part(part: ModelResponsePart) -> ModelResponsePart:
    if _part_emotion(part):
        assert isinstance(part, TextPart)
        return replace(part, content=_strip_text(part.content))
    return part


def _strip_text(text: str) -> str:
    """*text* without the emotion emoji it opens with, nor the space after."""
    return text.lstrip()[1:].lstrip()
