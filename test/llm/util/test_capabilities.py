from unittest.mock import MagicMock

import pytest

from zrb.llm.util.capabilities import (
    ModelCapabilities,
    ModelCapabilityRegistry,
    is_known_model,
    media_type_modality,
    model_capabilities,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure user-registered overrides don't leak between tests."""
    model_capabilities.clear()
    yield
    model_capabilities.clear()


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
def test_image_input_supported_for_known_vision_models(model_name):
    assert model_capabilities.get(model_name).supports_image_input is True


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
def test_image_input_unsupported_for_text_only_models(model_name):
    assert model_capabilities.get(model_name).supports_image_input is False


def test_audio_input_recognised_for_audio_capable_models():
    assert model_capabilities.get("openai:gpt-4o").supports_audio_input is True
    assert (
        model_capabilities.get("openai:gpt-4o-mini-audio").supports_audio_input is True
    )
    assert model_capabilities.get("google:gemini-1.5-pro").supports_audio_input is True
    assert model_capabilities.get("ollama:qwen2-audio").supports_audio_input is True


def test_audio_input_unsupported_for_non_audio_models():
    assert model_capabilities.get("openai:gpt-3.5-turbo").supports_audio_input is False
    assert (
        model_capabilities.get("anthropic:claude-opus-4-7").supports_audio_input
        is False
    )
    assert model_capabilities.get("ollama:llava").supports_audio_input is False


def test_video_input_only_for_gemini_class():
    assert (
        model_capabilities.get("google:gemini-1.5-flash").supports_video_input is True
    )
    assert model_capabilities.get("google:gemini-2.0-pro").supports_video_input is True
    assert model_capabilities.get("openai:gpt-4o").supports_video_input is False
    assert (
        model_capabilities.get("anthropic:claude-opus-4-7").supports_video_input
        is False
    )


def test_parallel_tool_calls_unknown_for_general_models():
    # Most models have no explicit entry → tri-state ``None`` ("unknown").
    assert model_capabilities.get("openai:gpt-4o").supports_parallel_tool_calls is None
    assert (
        model_capabilities.get(
            "anthropic:claude-sonnet-4-6"
        ).supports_parallel_tool_calls
        is None
    )


@pytest.mark.parametrize(
    "model_name",
    [
        "ollama:minimax-m2.7:cloud",
        "ollama:glm-4.7:cloud",
    ],
)
def test_parallel_tool_calls_known_unsupported_models(model_name):
    assert model_capabilities.get(model_name).supports_parallel_tool_calls is False


def test_get_returns_defaults_for_none_and_empty():
    defaults = ModelCapabilities()
    assert model_capabilities.get(None) == defaults
    assert model_capabilities.get("") == defaults


def test_supports_modality_returns_false_for_unknown_modality_string():
    # An unknown modality argument returns False (defensive).
    assert (
        model_capabilities.supports_modality("openai:gpt-4o", "lidar") is False  # type: ignore[arg-type]
    )


def test_supports_modality_dispatches_per_modality():
    assert model_capabilities.supports_modality("openai:gpt-4o", "image") is True
    assert model_capabilities.supports_modality("openai:gpt-4o", "audio") is True
    assert model_capabilities.supports_modality("openai:gpt-4o", "video") is False
    assert (
        model_capabilities.supports_modality("google:gemini-2.0-pro", "video") is True
    )


def test_pydantic_ai_model_instance_resolved_via_model_name():
    fake = MagicMock()
    fake.model_name = "gpt-4o-mini"
    assert model_capabilities.get(fake).supports_image_input is True


def test_magic_mock_without_real_string_name_treated_as_unknown():
    mock = MagicMock()  # both .model_name and .name return MagicMock
    assert is_known_model(mock) is False
    assert model_capabilities.get(mock) == ModelCapabilities()


def test_is_known_model_truthiness():
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
def test_media_type_modality_maps_mime_heads(media_type, expected):
    assert media_type_modality(media_type) == expected


def test_register_override_takes_priority_over_pattern_table():
    # gpt-4o normally supports image input — pretend the user knows their
    # deployment doesn't expose that and disables it locally.
    model_capabilities.register("gpt-4o", supports_image_input=False)
    assert model_capabilities.get("openai:gpt-4o").supports_image_input is False


def test_register_override_is_partial():
    # Overriding one field must not reset the others to dataclass defaults.
    model_capabilities.register("gpt-4o", supports_parallel_tool_calls=False)
    caps = model_capabilities.get("openai:gpt-4o")
    assert caps.supports_parallel_tool_calls is False
    assert caps.supports_image_input is True
    assert caps.supports_audio_input is True


def test_register_unknown_field_raises_type_error():
    with pytest.raises(TypeError, match="Unknown capability field"):
        model_capabilities.register("anything", supports_nonsense=True)


def test_register_most_recent_wins():
    model_capabilities.register("gpt-4o", supports_image_input=False)
    model_capabilities.register("gpt-4o", supports_image_input=True)
    assert model_capabilities.get("openai:gpt-4o").supports_image_input is True


def test_clear_drops_overrides_but_preserves_builtins():
    model_capabilities.register("gpt-4o", supports_image_input=False)
    model_capabilities.clear()
    # built-in pattern still applies after clear()
    assert model_capabilities.get("openai:gpt-4o").supports_image_input is True


def test_override_can_force_parallel_tool_calls_back_on():
    # A user can opt minimax back into parallel calls if they know better
    # than the built-in deny entry.
    model_capabilities.register("minimax-m2\\.7", supports_parallel_tool_calls=None)
    caps = model_capabilities.get("ollama:minimax-m2.7:cloud")
    assert caps.supports_parallel_tool_calls is None


def test_override_pattern_is_case_insensitive():
    model_capabilities.register("GPT-4O", supports_image_input=False)
    assert model_capabilities.get("openai:gpt-4o").supports_image_input is False


def test_separate_registry_instances_have_independent_state():
    # Constructing a fresh registry is the recommended pattern for
    # tests that need full isolation from the module-level singleton.
    isolated = ModelCapabilityRegistry()
    isolated.register("gpt-4o", supports_image_input=False)

    assert isolated.get("openai:gpt-4o").supports_image_input is False
    # The module-level singleton is unaffected.
    assert model_capabilities.get("openai:gpt-4o").supports_image_input is True
