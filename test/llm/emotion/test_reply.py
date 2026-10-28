"""The emotion emoji taken out of a real pydantic-ai run's reply, streamed and final."""

from unittest.mock import MagicMock

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelResponse,
    PartDeltaEvent,
    PartEndEvent,
    PartStartEvent,
    TextPart,
)
from pydantic_ai.models.function import FunctionModel

from zrb.llm.ambient_state import current_reply_emotion
from zrb.llm.emotion.reply import ReplyEmotion


def _model(*chunks: str) -> FunctionModel:
    async def stream(messages, info):
        for chunk in chunks:
            yield chunk

    return FunctionModel(stream_function=stream)


async def _run(*chunks: str):
    """The text the stream handler saw, what the run kept, and what was read."""
    read: list[str] = []
    started: list[bool] = []
    seen: list[str] = []
    emotion_seen_with_text: list[str] = []

    async def on_emotion(emotion):
        read.append(emotion)

    async def on_stream_start():
        started.append(True)

    async def handler(ctx, events):
        async for event in events:
            text = ""
            if isinstance(event, PartStartEvent):
                text = getattr(event.part, "content", "")
            elif isinstance(event, PartDeltaEvent):
                text = getattr(event.delta, "content_delta", "")
            if text:
                seen.append(text)
                emotion_seen_with_text.append(current_reply_emotion.get())

    capability = ReplyEmotion(on_emotion, on_stream_start)
    agent = Agent(_model(*chunks), capabilities=[capability])
    token = current_reply_emotion.set("")
    try:
        result = await agent.run("hi", event_stream_handler=handler)
    finally:
        current_reply_emotion.reset(token)
    kept = [
        part.content
        for message in result.all_messages()
        if isinstance(message, ModelResponse)
        for part in message.parts
    ]
    return "".join(seen), result.output, kept, read, started, emotion_seen_with_text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "chunks",
    [
        ("😊 Hello", " world."),
        ("", "😊", " Hello", " world."),
        ("  ", "😊 Hel", "lo world."),
    ],
)
async def test_the_emoji_is_out_of_every_copy_of_the_reply(chunks):
    seen, output, kept, read, started, with_text = await _run(*chunks)

    assert seen == "Hello world."
    assert output == "Hello world."
    assert kept == ["Hello world."]
    assert read == ["happy"]
    assert started and all(started)
    assert set(with_text) == {"happy"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "chunks",
    [
        ("**😊 Hello", " world.**"),
        ("**", "😊", " Hel", "lo world.**"),
        ("**😊", "\n\nHello", " world.**"),
    ],
)
async def test_an_emoji_inside_the_replys_opening_markdown_is_read_and_taken_out(chunks):
    """A reply that opens with bold around the emoji (`**😊 …`, which a model
    writes by habit) still opens with an emotion, and only the emoji leaves:
    the markers stay, so the emphasis keeps both halves."""
    seen, output, kept, read, started, with_text = await _run(*chunks)

    assert seen == "**Hello world.**"
    assert output == "**Hello world.**"
    assert kept == ["**Hello world.**"]
    assert read == ["happy"]
    assert started and all(started)
    assert set(with_text) == {"happy"}


@pytest.mark.asyncio
async def test_the_end_event_of_a_stripped_part_carries_the_stripped_text():
    """A UI may paint from the end event: it must not put the emoji back."""
    read: list[str] = []

    async def on_emotion(emotion):
        read.append(emotion)

    async def events():
        yield PartStartEvent(index=0, part=TextPart("**😊 Hello"))
        yield PartEndEvent(index=0, part=TextPart("**😊 Hello world.**"))

    capability = ReplyEmotion(on_emotion, _noop)
    passed = [
        event
        async for event in capability.wrap_run_event_stream(
            MagicMock(), stream=events()
        )
    ]

    ends = [event for event in passed if isinstance(event, PartEndEvent)]
    assert [event.part.content for event in ends] == ["**Hello world.**"]
    assert read == ["happy"]


@pytest.mark.asyncio
async def test_a_reply_without_an_emotion_emoji_is_left_as_it_is():
    seen, output, kept, read, _, with_text = await _run("🚀 Ship", " it 😊")

    assert seen == "🚀 Ship it 😊"
    assert output == "🚀 Ship it 😊"
    assert kept == ["🚀 Ship it 😊"]
    assert read == []
    assert set(with_text) == {""}


@pytest.mark.asyncio
async def test_a_reply_of_only_spaces_passes_through():
    seen, output, _, read, _, _ = await _run(" ", " ")

    assert read == []
    assert seen.strip() == output.strip() == ""


async def _noop(*_):
    return None


@pytest.mark.asyncio
async def test_a_run_without_an_emotion_keeps_the_turns():
    """A turn is more than one run: the round after a tool call carries no
    emoji, and clearing it there dropped the turn's voice mid-reply. Clearing
    a turn's emotion is `EmotionSession`'s job, done when the turn starts."""
    replies = iter(["😊 Hello.", "Plain words."])

    def respond(messages, info):
        return ModelResponse(parts=[TextPart(next(replies))])

    async def stream(messages, info):
        yield next(replies)

    model = FunctionModel(respond, stream_function=stream)
    agent = Agent(model, capabilities=[ReplyEmotion(_noop, _noop)])
    token = current_reply_emotion.set("")
    try:
        first = await agent.run("hi")
        after_first = current_reply_emotion.get()
        await agent.run("again")
        after_second = current_reply_emotion.get()
    finally:
        current_reply_emotion.reset(token)

    assert first.output == "Hello."
    assert after_first == "happy"
    assert after_second == "happy"


_TWO_TEXTS = [TextPart("Here is the result:"), TextPart("😊 literal content")]


@pytest.mark.asyncio
async def test_only_the_first_text_of_a_streamed_reply_gives_its_emotion():
    """A later text part keeps an emoji it opens with (PR #633 review)."""
    read: list[str] = []

    async def on_emotion(emotion):
        read.append(emotion)

    async def events():
        for index, part in enumerate(_TWO_TEXTS):
            yield PartStartEvent(index=index, part=part)
            yield PartEndEvent(index=index, part=part)

    capability = ReplyEmotion(on_emotion, _noop)
    passed = [
        event
        async for event in capability.wrap_run_event_stream(
            MagicMock(), stream=events()
        )
    ]

    assert [e.part.content for e in passed if isinstance(e, PartStartEvent)] == [
        "Here is the result:",
        "😊 literal content",
    ]
    assert read == []


@pytest.mark.asyncio
async def test_only_the_first_text_of_a_finished_reply_loses_its_emoji():
    response = ModelResponse(parts=list(_TWO_TEXTS))
    capability = ReplyEmotion(_noop, _noop)

    kept = await capability.after_model_request(
        MagicMock(), request_context=MagicMock(), response=response
    )

    assert kept is response
