"""Taking the emotion emoji out of the model's reply, wherever the reply goes.

The model opens its reply with an emoji for how it feels (`emotion_live`).
`ReplyEmotion` is a pydantic-ai capability that removes it from both copies
of the reply: the streamed events every UI, speech and observer read
(`wrap_run_event_stream`), and the finished response the output, history and
hooks are made from (`after_model_request`). The emotion is kept as state
instead (`current_reply_emotion`), so the user never sees the emoji. It is
kept for the whole turn: a run whose text opens with no emoji leaves it
alone, and the session clears it when the next turn starts.

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
from zrb.llm.emotion.label import (
    OPENING_MARKERS,
    get_leading_emotion,
    leading_emoji_index,
    opening_tag_index,
)
from zrb.llm.util.spoken import OPEN_TAG, partial_marker


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
        # Only the first text part with something to read can carry the emoji.
        # A part that is nothing but markers is not it: the stream does not
        # treat one as the opening either, and the two copies must agree.
        index = next(
            (
                i
                for i, part in enumerate(response.parts)
                if isinstance(part, TextPart) and _has_visible_text(part.content)
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
        # Read once per run, and a turn is more than one run: every round after
        # a tool call carries no emoji. Clearing here would drop the turn's
        # emotion mid-reply, so the session clears it when a turn starts.
        if not emotion:
            return
        current_reply_emotion.set(emotion)
        await self._on_emotion(emotion)


class _Opening:
    """Buffers a response's events from the start of its first text part
    until that part carries a word past its opening, then releases them in
    order with the emoji removed. Later text parts pass through untouched.

    Holding until a word arrives is what makes the removal decidable: `**😊`
    may still close as `**😊**`, where the whole enclosure goes, and deciding
    before the closer arrives would leave `****` behind.

    `take` and `flush` return the events to pass on. A `str` among them is
    the emotion read, ``""`` when the reply opens without one, which leaves
    the turn's emotion as it is."""

    def __init__(self) -> None:
        self._held: list[AgentStreamEvent] = []
        self._index: int | None = None
        self._text = ""
        # Indexes of parts whose emoji was removed, so their end event is
        # stripped too.
        self._stripped: set[int] = set()
        # True once the opening has been read; later parts pass untouched.
        self._is_opening_read = False

    def take(self, event: AgentStreamEvent) -> "list[AgentStreamEvent | str]":
        if (
            isinstance(event, PartStartEvent)
            and isinstance(event.part, TextPart)
            and not self._is_opening_read
        ):
            passed = self.flush()
            self._held = [event]
            self._index = event.index
            self._text = event.part.content
            return passed + self._release_if_a_word()
        if self._index is None:
            return [self._clean_end(event)]
        if isinstance(event, PartEndEvent) and event.index == self._index:
            return self.flush() + [self._clean_end(event)]
        self._held.append(event)
        if _is_text_delta(event, self._index):
            assert isinstance(event, PartDeltaEvent)
            assert isinstance(event.delta, TextPartDelta)
            self._text += event.delta.content_delta
            return self._release_if_a_word()
        return []

    def flush(self) -> "list[AgentStreamEvent | str]":
        """Release what is held. A part that never got a word goes out here,
        with its opening still taken out."""
        if self._index is None:
            held, self._held = self._held, []
            return list(held)
        return self._release_if_a_word(force=True)

    def _release_if_a_word(self, force: bool = False) -> "list[AgentStreamEvent | str]":
        if not force and not _has_a_word(self._text):
            return []
        index, held, text = self._index, self._held, self._text
        self._held, self._index, self._text = [], None, ""
        emotion = get_leading_emotion(text) or ""
        spans = _removed_spans(text)
        # A part that is only markers or blanks opened nothing, so the next
        # part can still be the reply's opening.
        if spans or _has_visible_text(text):
            self._is_opening_read = True
        if spans:
            assert index is not None
            self._stripped.add(index)
            held = _remove_chars(held, index, spans)
        return [emotion, *held]

    def _clean_end(self, event: AgentStreamEvent) -> AgentStreamEvent:
        if isinstance(event, PartEndEvent) and event.index in self._stripped:
            return replace(event, part=_strip_part(event.part))
        return event


def _removed_spans(text: str) -> "list[tuple[int, int]]":
    """The spans `_strip_text` takes out of *text*, or none when it opens with
    no emoji: the whitespace in front, then the emoji with the whitespace after
    it. Markdown markers in front of the emoji are kept, so emphasis keeps its
    closing pair — unless the emphasis holds nothing but the emoji, `**😊**`,
    where keeping them would leave four stray markers behind. The whitespace in
    front goes either way: it opened the reply, and it is gone before the text
    is read or spoken."""
    index = leading_emoji_index(text)
    if index is None:
        return []
    leading = len(text) - len(text.lstrip())
    before = text[leading:index]
    after = text[index + 1 :]
    if before and after.startswith(before):
        closer_end = index + 1 + len(before)
        return [(0, closer_end + _leading_space(text[closer_end:]))]
    spans = [(0, leading)] if leading else []
    spans.append((index, index + 1 + _leading_space(after)))
    return spans


def _leading_space(text: str) -> int:
    """How many characters of *text* are whitespace."""
    return len(text) - len(text.lstrip())


def _has_visible_text(text: str) -> bool:
    """False while *text* is only whitespace, markdown markers and the start of
    a `<spoken>` marker: the blanks a stream sends before its first word are not
    the start of the reply, and a block's own marker is not a word either — the
    emoji that may follow it is still to come."""
    index = opening_tag_index(text)
    if index is not None:
        text = text[index + len(OPEN_TAG) :]
    return bool(_without_partial_marker(text).strip(OPENING_MARKERS + " \t\r\n"))


def _without_partial_marker(text: str) -> str:
    """*text* without the tail that could still become a marker: `<spok` says
    nothing yet, and the emoji may be the very next character."""
    tail = partial_marker(text)
    return text[: len(text) - len(tail)]


def _has_a_word(text: str) -> bool:
    """Whether anything readable has arrived past the opening emoji. Until it
    has, markers around the emoji could still close straight after it, and
    what leaves the reply is not yet decidable."""
    return _has_visible_text(_strip_text(text))


def _remove_chars(
    events: list[AgentStreamEvent], index: int, spans: "list[tuple[int, int]]"
) -> list[AgentStreamEvent]:
    """*events* with *spans* of part *index*'s text gone, dropping a delta
    left empty."""
    offset = 0
    kept: list[AgentStreamEvent] = []
    for event in events:
        if (
            isinstance(event, PartStartEvent)
            and isinstance(event.part, TextPart)
            and event.index == index
        ):
            content, offset = _cut_spans(event.part.content, offset, spans)
            kept.append(replace(event, part=replace(event.part, content=content)))
        elif _is_text_delta(event, index):
            assert isinstance(event, PartDeltaEvent)
            assert isinstance(event.delta, TextPartDelta)
            delta = event.delta.content_delta
            content, offset = _cut_spans(delta, offset, spans)
            if delta and not content:
                continue
            kept.append(
                replace(event, delta=replace(event.delta, content_delta=content))
            )
        else:
            kept.append(event)
    return kept


def _cut_spans(
    content: str, offset: int, spans: "list[tuple[int, int]]"
) -> "tuple[str, int]":
    """*content*, which begins at *offset* in its part's text, with *spans*
    gone; and the offset just past it."""
    pieces: list[str] = []
    cursor = 0
    for start, end in spans:
        low = max(start - offset, cursor)
        high = min(end - offset, len(content))
        if high <= low:
            continue
        pieces.append(content[cursor:low])
        cursor = high
    pieces.append(content[cursor:])
    return "".join(pieces), offset + len(content)


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
    """*text* without the emotion emoji it opens with, nor the space after.
    One rule, in `_removed_spans`, so the streamed and finished copies of a
    reply cannot disagree about what leaves."""
    return _cut_spans(text, 0, _removed_spans(text))[0]
