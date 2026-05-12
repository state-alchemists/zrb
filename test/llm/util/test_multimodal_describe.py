from unittest.mock import patch

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
