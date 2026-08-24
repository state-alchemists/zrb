from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai.messages import BinaryContent

from zrb.llm.util.multimodal_describe import (
    describe_binary_attachment,
    replace_unsupported_attachments,
)


def _png() -> BinaryContent:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, format="PNG")
    return BinaryContent(data=buf.getvalue(), media_type="image/png")


def _audio() -> BinaryContent:
    return BinaryContent(data=b"RIFF\x24\x00\x00\x00WAVE", media_type="audio/wav")


def _video() -> BinaryContent:
    return BinaryContent(data=b"\x00\x00\x00\x18ftypmp42", media_type="video/mp4")


def _pdf() -> BinaryContent:
    return BinaryContent(data=b"%PDF-1.4 fake", media_type="application/pdf")


@pytest.mark.asyncio
async def test_passthrough_when_main_model_supports_image():
    image = _png()

    result = await replace_unsupported_attachments(
        ["hello", image], main_model="openai:gpt-4o", multimodal_model=None
    )

    assert isinstance(result, list)
    assert result[0] == "hello"
    assert result[1] is image


@pytest.mark.asyncio
async def test_passthrough_when_main_model_unidentifiable():
    """MagicMock-style models pass through to the provider unchanged."""
    image = _png()

    result = await replace_unsupported_attachments(
        ["hi", image], main_model=object(), multimodal_model=None
    )

    assert result[1] is image


@pytest.mark.asyncio
async def test_image_dropped_with_warning_when_no_multimodal_configured():
    image = _png()
    messages = []

    result = await replace_unsupported_attachments(
        ["hi", image],
        main_model="openai:gpt-3.5-turbo",
        multimodal_model=None,
        print_fn=lambda m: messages.append(m),
    )

    assert result == "hi"
    assert any("Dropped image" in m for m in messages)


@pytest.mark.asyncio
async def test_video_dropped_when_main_model_text_only():
    video = _video()
    messages = []

    result = await replace_unsupported_attachments(
        ["hi", video],
        main_model="openai:gpt-3.5-turbo",
        multimodal_model=None,
        print_fn=lambda m: messages.append(m),
    )

    assert result == "hi"
    assert any("Dropped video" in m for m in messages)


@pytest.mark.asyncio
async def test_video_kept_when_main_model_supports_video():
    video = _video()

    result = await replace_unsupported_attachments(
        ["hi", video], main_model="google:gemini-1.5-flash", multimodal_model=None
    )

    assert result[1] is video


@pytest.mark.asyncio
async def test_audio_dropped_when_main_model_text_only_no_fallback():
    audio = _audio()
    messages = []

    result = await replace_unsupported_attachments(
        ["transcribe", audio],
        main_model="anthropic:claude-haiku-3",  # text-only
        multimodal_model=None,
        print_fn=lambda m: messages.append(m),
    )

    assert result == "transcribe"
    assert any("Dropped audio" in m for m in messages)


@pytest.mark.asyncio
async def test_text_only_input_passes_through():
    assert await replace_unsupported_attachments(None, main_model="x") is None
    assert await replace_unsupported_attachments("text", main_model="x") == "text"


@pytest.mark.asyncio
async def test_image_substituted_with_description_when_fallback_succeeds():
    image = _png()
    messages = []

    async def fake_describe(binary, multimodal_model):
        return "A red 4x4 placeholder image."

    with patch(
        "zrb.llm.util.multimodal_describe.describe_binary_attachment",
        side_effect=fake_describe,
    ):
        result = await replace_unsupported_attachments(
            ["look", image],
            main_model="openai:gpt-3.5-turbo",
            multimodal_model="openai:gpt-4o-mini",
            print_fn=lambda m: messages.append(m),
        )

    # Both pieces remain text → list collapses to a joined string.
    assert isinstance(result, str)
    assert "look" in result
    assert "Image attachment" in result
    assert "red 4x4" in result
    assert any("described via multimodal" in m for m in messages)


@pytest.mark.asyncio
async def test_image_dropped_when_multimodal_describe_fails():
    image = _png()
    messages = []

    async def fail_describe(binary, multimodal_model):
        return None

    with patch(
        "zrb.llm.util.multimodal_describe.describe_binary_attachment",
        side_effect=fail_describe,
    ):
        result = await replace_unsupported_attachments(
            ["look", image],
            main_model="openai:gpt-3.5-turbo",
            multimodal_model="openai:gpt-4o-mini",
            print_fn=lambda m: messages.append(m),
        )

    assert result == "look"
    assert any("Dropped image" in m for m in messages)


@pytest.mark.asyncio
async def test_document_dropped_when_main_model_text_only():
    """A raw PDF (extraction-failure fallback) is not silently passed through."""
    pdf = _pdf()
    messages = []

    result = await replace_unsupported_attachments(
        ["read this", pdf],
        main_model="openai:gpt-3.5-turbo",
        multimodal_model=None,
        print_fn=lambda m: messages.append(m),
    )

    assert result == "read this"
    assert any("Dropped document" in m for m in messages)
    assert any("cannot be auto-described" in m for m in messages)


@pytest.mark.asyncio
async def test_document_kept_when_main_model_supports_documents():
    pdf = _pdf()

    result = await replace_unsupported_attachments(
        ["read this"], main_model="openai:gpt-4o", multimodal_model=None
    )
    result_with_pdf = await replace_unsupported_attachments(
        ["read this", pdf], main_model="openai:gpt-4o", multimodal_model=None
    )

    # An all-string list collapses to plain text (see the function's
    # docstring/comment) — only the mixed list stays a list.
    assert result == "read this"
    assert result_with_pdf[1] is pdf


@pytest.mark.asyncio
async def test_document_never_auto_described_even_with_multimodal_model():
    """describe_binary_attachment only handles image/audio — documents always drop."""
    pdf = _pdf()

    described = await describe_binary_attachment(
        pdf, multimodal_model="openai:gpt-4o-mini"
    )

    assert described is None


@pytest.mark.asyncio
async def test_describe_returns_none_for_unsupported_modality():
    video = _video()

    result = await describe_binary_attachment(
        video, multimodal_model="openai:gpt-4o-mini"
    )

    assert result is None


@pytest.mark.asyncio
async def test_describe_returns_none_when_no_multimodal_configured():
    image = _png()

    result = await describe_binary_attachment(image, multimodal_model=None)

    assert result is None


@pytest.mark.asyncio
async def test_describe_returns_none_when_multimodal_model_lacks_modality():
    audio = _audio()

    # claude-haiku-3 is text-only, so even as the "describer" it cannot transcribe.
    result = await describe_binary_attachment(
        audio, multimodal_model="anthropic:claude-haiku-3"
    )

    assert result is None


class _FakeResult:
    def __init__(self, text: str):
        self.text = text

    def __str__(self):
        return self.text


@pytest.mark.asyncio
async def test_describe_runs_sub_agent_and_returns_text_for_image():
    """The happy path: a one-shot agent is built with the image prompt and the
    binary attached, and its output is returned trimmed."""
    image = _png()
    captured = {}

    def fake_create_agent(model=None, system_prompt=None, **kwargs):
        captured["model"] = model
        captured["system_prompt"] = system_prompt
        return MagicMock()

    async def fake_run_agent(agent, message, message_history, limiter, attachments):
        captured["message"] = message
        captured["attachments"] = attachments
        return _FakeResult("  a red square  "), None

    with (
        patch("zrb.llm.agent.create_agent", side_effect=fake_create_agent),
        patch("zrb.llm.agent.run_agent", side_effect=fake_run_agent),
        patch(
            "zrb.llm.config.config.llm_config.resolve_model",
            side_effect=lambda m: f"resolved:{m}",
        ),
    ):
        described = await describe_binary_attachment(
            image, multimodal_model="openai:gpt-4o-mini"
        )

    assert described == "a red square"
    assert captured["model"] == "resolved:openai:gpt-4o-mini"
    assert "image" in captured["system_prompt"].lower()
    assert "Describe the attached image" in captured["message"]
    assert captured["attachments"] == [image]


@pytest.mark.asyncio
async def test_describe_uses_audio_prompt_for_audio_binary():
    audio = _audio()
    prompts = []

    def fake_create_agent(system_prompt=None, **kwargs):
        prompts.append(system_prompt)
        return MagicMock()

    async def fake_run_agent(**kwargs):
        return _FakeResult("someone speaking"), None

    with (
        patch("zrb.llm.agent.create_agent", side_effect=fake_create_agent),
        patch("zrb.llm.agent.run_agent", side_effect=fake_run_agent),
        patch(
            "zrb.llm.config.config.llm_config.resolve_model",
            side_effect=lambda m: m,
        ),
    ):
        described = await describe_binary_attachment(
            audio, multimodal_model="openai:gpt-4o-audio"
        )

    assert described == "someone speaking"
    assert "audio" in prompts[0].lower()


@pytest.mark.asyncio
async def test_describe_returns_none_when_sub_agent_run_fails():
    image = _png()

    async def failing_run_agent(**kwargs):
        raise RuntimeError("provider down")

    with (
        patch("zrb.llm.agent.create_agent", return_value=MagicMock()),
        patch("zrb.llm.agent.run_agent", side_effect=failing_run_agent),
        patch(
            "zrb.llm.config.config.llm_config.resolve_model",
            side_effect=lambda m: m,
        ),
    ):
        described = await describe_binary_attachment(
            image, multimodal_model="openai:gpt-4o-mini"
        )

    assert described is None


@pytest.mark.asyncio
async def test_replace_keeps_non_list_non_string_input_untouched():
    """Tuples and other sequence types pass through without interpretation."""
    payload = ("keep", "me")
    result = await replace_unsupported_attachments(payload, main_model="x")
    assert result is payload
