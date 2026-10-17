"""The emotion emoji taken out of a real pydantic-ai run's reply, streamed and final."""

import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelResponse,
    PartDeltaEvent,
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
async def test_a_reply_without_an_emotion_does_not_keep_the_last_one():
    """Even run without a stream handler: the capability makes every run
    stream, and a text part opening with no emotion clears it."""
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
    assert after_second == ""
