from unittest.mock import MagicMock

import pytest

from zrb.llm.util.modality import (
    is_known_model,
    media_type_modality,
    supports_audio,
    supports_image,
    supports_modality,
    supports_video,
)


@pytest.mark.parametrize(
    "model_name",
    [
        "openai:gpt-4o",
        "openai:gpt-4o-mini",
        "openai:gpt-4-turbo",
        "openai:gpt-5",
        "anthropic:claude-haiku-3.5",
        "anthropic:claude-sonnet-4-6",
        "anthropic:claude-opus-4-7",
        "google:gemini-1.5-flash",
        "google:gemini-2.0-pro",
        "ollama:llava",
        "ollama:pixtral-12b",
    ],
)
def test_supports_image_true_for_known_vision_models(model_name):
    assert supports_image(model_name) is True


@pytest.mark.parametrize(
    "model_name",
    [
        "openai:gpt-3.5-turbo",
        "openai:gpt-4-0314",
        "openai:gpt-4-0613",
        "anthropic:claude-haiku-3",
        "anthropic:claude-instant-1",
        "ollama:llama3:8b",
        "ollama:qwen2.5",
    ],
)
def test_supports_image_false_for_text_only_models(model_name):
    assert supports_image(model_name) is False


def test_supports_audio_recognises_audio_capable_models():
    assert supports_audio("openai:gpt-4o") is True
    assert supports_audio("openai:gpt-4o-mini-audio") is True
    assert supports_audio("google:gemini-1.5-pro") is True
    assert supports_audio("ollama:qwen2-audio") is True


def test_supports_audio_false_for_non_audio_models():
    assert supports_audio("openai:gpt-3.5-turbo") is False
    assert supports_audio("anthropic:claude-opus-4-7") is False
    assert supports_audio("ollama:llava") is False


def test_supports_video_only_for_gemini_class():
    assert supports_video("google:gemini-1.5-flash") is True
    assert supports_video("google:gemini-2.0-pro") is True
    assert supports_video("openai:gpt-4o") is False
    assert supports_video("anthropic:claude-opus-4-7") is False


def test_supports_modality_returns_false_for_none_and_empty():
    assert supports_image(None) is False
    assert supports_image("") is False
    assert supports_modality("openai:gpt-4o", "image") is True


def test_unknown_modality_returns_false():
    assert supports_modality("openai:gpt-4o", "lidar") is False  # type: ignore[arg-type]


def test_supports_image_handles_pydantic_ai_model_instance():
    fake_model = MagicMock()
    fake_model.model_name = "gpt-4o-mini"

    assert supports_image(fake_model) is True


def test_magic_mock_without_real_string_name_is_treated_as_unknown():
    mock_model = MagicMock()  # both .model_name and .name return MagicMock

    assert is_known_model(mock_model) is False
    assert supports_image(mock_model) is False


def test_is_known_model_true_for_real_string():
    assert is_known_model("openai:gpt-4o") is True
    assert is_known_model(None) is False
    assert is_known_model("") is False


@pytest.mark.parametrize(
    "media_type, expected",
    [
        ("image/png", "image"),
        ("image/jpeg", "image"),
        ("audio/wav", "audio"),
        ("audio/mpeg", "audio"),
        ("video/mp4", "video"),
        ("application/pdf", None),
        ("text/plain", None),
        ("", None),
    ],
)
def test_media_type_modality(media_type, expected):
    assert media_type_modality(media_type) == expected
