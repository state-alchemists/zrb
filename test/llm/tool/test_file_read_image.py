"""`Read` on an image file: attached for the model, or refused with a reason."""

import io
import os

import pytest

from zrb.config.config import CFG
from zrb.llm.agent_state import current_model
from zrb.llm.tool.file import read_file


def _save_image(path, size=(4, 4), image_format="PNG") -> str:
    from PIL import Image

    Image.new("RGB", size, "red").save(path, format=image_format)
    return str(path)


@pytest.fixture
def vision_model():
    token = current_model.set("openai:gpt-4o")
    yield
    current_model.reset(token)


@pytest.fixture
def text_only_model():
    token = current_model.set("openai:gpt-3.5-turbo")
    yield
    current_model.reset(token)


@pytest.mark.asyncio
async def test_an_image_is_attached_for_a_model_that_reads_images(
    tmp_path, vision_model
):
    path = _save_image(tmp_path / "shot.png")

    result = await read_file(path)

    assert result.return_value == f"Image file {path} read; it is attached."
    (image,) = result.content
    assert image.media_type == "image/png"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name, image_format",
    [("photo.jpg", "JPEG"), ("anim.gif", "GIF"), ("pic.webp", "WEBP")],
)
async def test_every_supported_image_type_is_attached(
    tmp_path, vision_model, name, image_format
):
    path = _save_image(tmp_path / name, image_format=image_format)

    result = await read_file(path)

    (image,) = result.content
    assert image.media_type.startswith("image/")


@pytest.mark.asyncio
async def test_line_range_arguments_do_not_apply_to_an_image(tmp_path, vision_model):
    path = _save_image(tmp_path / "shot.png")

    result = await read_file(path, start_line=5, end_line=2)

    assert len(result.content) == 1


@pytest.mark.asyncio
async def test_a_large_image_is_scaled_before_it_is_attached(
    tmp_path, vision_model, monkeypatch
):
    from PIL import Image

    monkeypatch.setattr(CFG, "LLM_MAX_IMAGE_DIMENSION", 100)
    path = _save_image(tmp_path / "wide.png", size=(1000, 50))

    result = await read_file(path)

    (image,) = result.content
    assert max(Image.open(io.BytesIO(image.data)).size) <= 100


@pytest.mark.asyncio
async def test_a_text_only_model_gets_the_image_described(
    tmp_path, text_only_model, monkeypatch
):
    async def describe(binary, multimodal_model):
        return "a red square"

    monkeypatch.setattr(CFG, "LLM_MULTIMODAL_MODEL", "openai:gpt-4o-mini")
    monkeypatch.setattr(
        "zrb.llm.agent.run.multimodal_describe.describe_binary_attachment", describe
    )
    path = _save_image(tmp_path / "shot.png")

    result = await read_file(path)

    assert result.startswith(f"Image file {path} read.")
    assert "a red square" in result


@pytest.mark.asyncio
async def test_a_text_only_model_without_a_describer_is_told_why(
    tmp_path, text_only_model, monkeypatch
):
    monkeypatch.setattr(CFG, "LLM_MULTIMODAL_MODEL", "")
    path = _save_image(tmp_path / "shot.png")

    result = await read_file(path)

    assert "you cannot see it" in result
    assert "LLM_MULTIMODAL_MODEL" in result


@pytest.mark.asyncio
async def test_reading_images_can_be_turned_off(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_ENABLE_READ_IMAGE", False)
    path = _save_image(tmp_path / "shot.png")

    result = await read_file(path)

    assert "[SYSTEM SUGGESTION]" in result
    assert "LLM_ENABLE_READ_IMAGE" in result


@pytest.mark.asyncio
async def test_an_image_over_the_attachment_cap_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(CFG, "LLM_MAX_ATTACHMENT_BYTES", 10)
    path = _save_image(tmp_path / "shot.png")

    result = await read_file(path)

    assert "too large" in result
    assert "LLM_MAX_ATTACHMENT_BYTES" in result


@pytest.mark.asyncio
async def test_an_image_too_large_to_decode_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr("zrb.llm.util.image_scale.MAX_DECODE_PIXELS", 100)
    path = _save_image(tmp_path / "huge.png", size=(20, 20))

    result = await read_file(path)

    assert "too large to decode safely" in result
    assert "[SYSTEM SUGGESTION]" in result


@pytest.mark.asyncio
async def test_a_file_whose_bytes_contradict_its_extension_is_refused(tmp_path):
    path = tmp_path / "fake.png"
    path.write_text("just text")

    result = await read_file(str(path))

    assert "not a readable image/png image" in result
    assert "[SYSTEM SUGGESTION]" in result


@pytest.mark.asyncio
async def test_a_corrupt_image_is_refused_rather_than_sent(tmp_path):
    path = tmp_path / "broken.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

    result = await read_file(str(path))

    assert "cannot be decoded" in result
    assert "[SYSTEM SUGGESTION]" in result


@pytest.mark.asyncio
@pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="root reads files regardless of mode",
)
async def test_an_unreadable_image_says_to_check_permissions(tmp_path):
    path = _save_image(tmp_path / "locked.png")
    os.chmod(path, 0)
    try:
        result = await read_file(path)
    finally:
        os.chmod(path, 0o600)

    assert "read permissions" in result
