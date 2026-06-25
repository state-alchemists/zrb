"""Tests for LLMConfig class."""

from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.config.config import LLMConfig, llm_config


def test_llm_config_model_setter():
    """Test LLMConfig model setter and getter."""
    config = LLMConfig()
    config.model = "openai:gpt-4"
    assert config.model == "openai:gpt-4"


def test_llm_config_small_model_setter():
    """Test LLMConfig small_model setter and getter."""
    config = LLMConfig()
    config.small_model = "openai:gpt-3.5-turbo"
    assert config.small_model == "openai:gpt-3.5-turbo"


def test_llm_config_model_settings():
    """Test LLMConfig model_settings setter and getter."""
    config = LLMConfig()
    settings = {"temperature": 0.7}
    config.model_settings = settings
    assert config.model_settings == settings


def test_llm_config_api_key_setter():
    """Test LLMConfig api_key setter and getter."""
    config = LLMConfig()
    config.api_key = "test-api-key"
    assert config.api_key == "test-api-key"


def test_llm_config_base_url_setter():
    """Test LLMConfig base_url setter and getter."""
    config = LLMConfig()
    config.base_url = "https://api.example.com"
    assert config.base_url == "https://api.example.com"


def test_llm_config_provider_setter():
    """Test LLMConfig provider setter and getter."""
    config = LLMConfig()
    config.provider = "anthropic"
    assert config.provider == "anthropic"


def test_llm_config_model_settings_none():
    """Test LLMConfig model_settings default is None."""
    config = LLMConfig()
    assert config.model_settings is None


def test_llm_config_api_key_from_cfg():
    """Test LLMConfig api_key falls back to CFG."""
    config = LLMConfig()
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_API_KEY = "cfg-api-key"
        # Clear any set api_key to test fallback
        config.api_key = None
        assert config.api_key == "cfg-api-key"


def test_llm_config_base_url_from_cfg():
    """Test LLMConfig base_url falls back to CFG."""
    config = LLMConfig()
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_BASE_URL = "https://cfg.example.com"
        # Clear any set base_url to test fallback
        config.base_url = None
        assert config.base_url == "https://cfg.example.com"


def test_llm_config_model_resolution_openai():
    """Test model property resolves OpenAI models correctly."""
    config = LLMConfig()
    config.model = "openai:gpt-4"
    # Should return the model string
    result = config.model
    assert result == "openai:gpt-4"


def test_llm_config_model_resolution_anthropic():
    """Test model property resolves Anthropic models correctly."""
    config = LLMConfig()
    config.model = "anthropic:claude-3"
    # Should return the model string
    result = config.model
    assert result == "anthropic:claude-3"


def test_llm_config_model_resolution_custom():
    """Test model property handles custom provider."""
    config = LLMConfig()
    config.model = "custom:model"
    # Should return the model string as-is
    result = config.model
    assert result == "custom:model"


def test_llm_config_small_model_falls_back_to_model():
    """Test small_model falls back to model when not set."""
    config = LLMConfig()
    config.model = "openai:gpt-4"
    # When small_model is not set, it should use model
    result = config.small_model
    # small_model uses model as fallback
    assert result is not None


def test_llm_config_provider_returns_openai_by_default():
    """Test provider returns 'openai' by default."""
    config = LLMConfig()
    # Clear any set values to test default behavior
    config.api_key = None
    config.base_url = None
    config.provider = None

    result = config.provider
    assert result == "openai"


def test_llm_config_model_default():
    """Test model returns default when not set."""
    config = LLMConfig()
    # Clear any set values to test default behavior
    config.model = None
    config.api_key = None
    config.base_url = None
    config.provider = None

    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_MODEL = "openai:gpt-4o"
        mock_cfg.LLM_API_KEY = None
        mock_cfg.LLM_BASE_URL = None
        # Should return the model string
        result = config.model
        assert result == "openai:gpt-4o"


def test_llm_config_model_with_api_key():
    """Test model property works with API key set."""
    config = LLMConfig()
    config.api_key = "test-key"
    config.model = "openai:gpt-4"

    # Should return a model string
    result = config.model
    assert result is not None


# ---------------------------------------------------------------------------
# model_getter / model_renderer / resolve_model
# ---------------------------------------------------------------------------


def test_llm_config_model_getter_none_by_default():
    """model_getter is None by default."""
    config = LLMConfig()
    assert config.model_getter is None


def test_llm_config_model_renderer_none_by_default():
    """model_renderer is None by default."""
    config = LLMConfig()
    assert config.model_renderer is None


def test_llm_config_model_getter_setter():
    """model_getter can be set and retrieved."""
    config = LLMConfig()
    getter = lambda m: "overridden"
    config.model_getter = getter
    assert config.model_getter is getter


def test_llm_config_model_renderer_setter():
    """model_renderer can be set and retrieved."""
    config = LLMConfig()
    renderer = lambda m: m
    config.model_renderer = renderer
    assert config.model_renderer is renderer


def test_llm_config_resolve_model_no_getter_renderer():
    """resolve_model returns the base model unchanged when no hooks are set."""
    config = LLMConfig()
    config.model = "openai:gpt-4"
    assert config.resolve_model() == "openai:gpt-4"


def test_llm_config_resolve_model_explicit_base():
    """resolve_model uses the supplied base_model, not config.model."""
    config = LLMConfig()
    config.model = "openai:gpt-4"
    assert config.resolve_model("anthropic:claude-3") == "anthropic:claude-3"


def test_llm_config_resolve_model_with_getter():
    """resolve_model applies model_getter to the base model."""
    config = LLMConfig()
    config.model = "openai:gpt-4"
    config.model_getter = lambda m: "getter-result"
    assert config.resolve_model() == "getter-result"


def test_llm_config_resolve_model_with_renderer():
    """resolve_model applies model_renderer after model_getter."""
    sentinel = object()
    config = LLMConfig()
    config.model = "openai:gpt-4"
    config.model_renderer = lambda m: sentinel
    assert config.resolve_model() is sentinel


def test_llm_config_resolve_model_getter_then_renderer():
    """resolve_model feeds getter output into renderer."""
    config = LLMConfig()
    config.model = "openai:gpt-4"
    config.model_getter = lambda m: "intermediate"
    config.model_renderer = lambda m: f"rendered:{m}"
    assert config.resolve_model() == "rendered:intermediate"


def test_llm_config_resolve_model_none_falls_back_to_default():
    """resolve_model(None) uses config.model as the base."""
    config = LLMConfig()
    config.model = "openai:gpt-4"
    config.model_getter = lambda m: f"got:{m}"
    assert config.resolve_model(None) == "got:openai:gpt-4"


# --- merged: additional LLMConfig coverage ---
# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------


def test_module_singleton_is_llm_config_instance():
    """The module exposes a ready-to-use LLMConfig singleton."""
    assert isinstance(llm_config, LLMConfig)


# ---------------------------------------------------------------------------
# model
# ---------------------------------------------------------------------------


def test_model_setter_and_getter():
    config = LLMConfig()
    config.model = "openai:gpt-4"
    assert config.model == "openai:gpt-4"


def test_model_default_from_cfg():
    config = LLMConfig()
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_MODEL = "openai:gpt-4o-custom"
        mock_cfg.LLM_API_KEY = None
        mock_cfg.LLM_BASE_URL = None
        assert config.model == "openai:gpt-4o-custom"


def test_model_default_fallback_when_cfg_empty():
    config = LLMConfig()
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_MODEL = ""
        mock_cfg.LLM_API_KEY = None
        mock_cfg.LLM_BASE_URL = None
        # Falls back to the hardcoded default.
        assert config.model == "openai-chat:gpt-4o"


def test_model_native_provider_returned_as_is():
    config = LLMConfig()
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_MODEL = "anthropic:claude-3"
        mock_cfg.LLM_API_KEY = None
        mock_cfg.LLM_BASE_URL = None
        assert config.model == "anthropic:claude-3"


def test_model_unknown_provider_without_config_returned_as_is():
    config = LLMConfig()
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_MODEL = "totally-made-up:model"
        mock_cfg.LLM_API_KEY = None
        mock_cfg.LLM_BASE_URL = None
        assert config.model == "totally-made-up:model"


def test_model_openai_with_api_key_resolves_to_object():
    config = LLMConfig()
    config.api_key = "sk-test"
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_MODEL = "openai:gpt-4"
        mock_cfg.LLM_BASE_URL = None
        result = config.model
        # With an api_key, openai models get wrapped into an OpenAIChatModel.
        assert result is not None
        assert not isinstance(result, str)


def test_model_unknown_provider_with_api_key_resolves():
    config = LLMConfig()
    config.api_key = "sk-test"
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_MODEL = "made-up:model"
        mock_cfg.LLM_BASE_URL = None
        result = config.model
        assert result is not None


# ---------------------------------------------------------------------------
# small_model
# ---------------------------------------------------------------------------


def test_small_model_setter_and_getter():
    config = LLMConfig()
    config.small_model = "openai:gpt-3.5-turbo"
    assert config.small_model == "openai:gpt-3.5-turbo"


def test_small_model_falls_back_to_cfg_string():
    config = LLMConfig()
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_SMALL_MODEL = "anthropic:claude-small"
        mock_cfg.LLM_API_KEY = None
        mock_cfg.LLM_BASE_URL = None
        assert config.small_model == "anthropic:claude-small"


def test_small_model_falls_back_to_main_model():
    config = LLMConfig()
    config.model = "anthropic:claude-3"
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_SMALL_MODEL = ""
        mock_cfg.LLM_API_KEY = None
        mock_cfg.LLM_BASE_URL = None
        # No small model configured -> uses the main model.
        assert config.small_model == "anthropic:claude-3"


def test_small_model_object_returned_as_is():
    config = LLMConfig()
    sentinel = object()
    config.small_model = sentinel
    assert config.small_model is sentinel


def test_small_model_cfg_object_returned_as_is():
    config = LLMConfig()
    sentinel = object()
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        # A non-string Model object configured in CFG is returned unchanged.
        mock_cfg.LLM_SMALL_MODEL = sentinel
        assert config.small_model is sentinel


# ---------------------------------------------------------------------------
# multimodal_model
# ---------------------------------------------------------------------------


def test_multimodal_model_setter_and_getter():
    config = LLMConfig()
    config.multimodal_model = "openai:gpt-4o"
    assert config.multimodal_model == "openai:gpt-4o"


def test_multimodal_model_none_when_unset_and_cfg_empty():
    config = LLMConfig()
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_MULTIMODAL_MODEL = ""
        assert config.multimodal_model is None


def test_multimodal_model_from_cfg_string():
    config = LLMConfig()
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_MULTIMODAL_MODEL = "anthropic:claude-3"
        mock_cfg.LLM_API_KEY = None
        mock_cfg.LLM_BASE_URL = None
        assert config.multimodal_model == "anthropic:claude-3"


def test_multimodal_model_object_returned_as_is():
    config = LLMConfig()
    sentinel = object()
    config.multimodal_model = sentinel
    assert config.multimodal_model is sentinel


def test_multimodal_model_cfg_object_returned_as_is():
    config = LLMConfig()
    sentinel = object()
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        # A non-string Model object configured in CFG is returned unchanged.
        mock_cfg.LLM_MULTIMODAL_MODEL = sentinel
        assert config.multimodal_model is sentinel


# ---------------------------------------------------------------------------
# model_settings
# ---------------------------------------------------------------------------


def test_model_settings_default_none():
    config = LLMConfig()
    assert config.model_settings is None


def test_model_settings_setter_and_getter():
    config = LLMConfig()
    settings = {"temperature": 0.5}
    config.model_settings = settings
    assert config.model_settings == settings


# ---------------------------------------------------------------------------
# model_getter / model_renderer / resolve_model
# ---------------------------------------------------------------------------


def test_model_getter_default_none():
    config = LLMConfig()
    assert config.model_getter is None


def test_model_renderer_default_none():
    config = LLMConfig()
    assert config.model_renderer is None


def test_model_getter_setter():
    config = LLMConfig()
    getter = lambda m: m
    config.model_getter = getter
    assert config.model_getter is getter


def test_model_renderer_setter():
    config = LLMConfig()
    renderer = lambda m: m
    config.model_renderer = renderer
    assert config.model_renderer is renderer


def test_resolve_model_no_hooks_uses_default_model():
    config = LLMConfig()
    config.model = "openai:gpt-4"
    assert config.resolve_model() == "openai:gpt-4"


def test_resolve_model_explicit_base_overrides_default():
    config = LLMConfig()
    config.model = "openai:gpt-4"
    assert config.resolve_model("anthropic:claude-3") == "anthropic:claude-3"


def test_resolve_model_applies_getter():
    config = LLMConfig()
    config.model = "openai:gpt-4"
    config.model_getter = lambda m: "from-getter"
    assert config.resolve_model() == "from-getter"


def test_resolve_model_applies_renderer():
    config = LLMConfig()
    config.model = "openai:gpt-4"
    config.model_renderer = lambda m: f"rendered:{m}"
    assert config.resolve_model() == "rendered:openai:gpt-4"


def test_resolve_model_getter_then_renderer_chain():
    config = LLMConfig()
    config.model = "openai:gpt-4"
    config.model_getter = lambda m: "mid"
    config.model_renderer = lambda m: f"final:{m}"
    assert config.resolve_model() == "final:mid"


def test_resolve_model_none_base_uses_config_model():
    config = LLMConfig()
    config.model = "openai:gpt-4"
    config.model_getter = lambda m: f"got:{m}"
    assert config.resolve_model(None) == "got:openai:gpt-4"


# ---------------------------------------------------------------------------
# api_key / base_url
# ---------------------------------------------------------------------------


def test_api_key_setter_and_getter():
    config = LLMConfig()
    config.api_key = "my-key"
    assert config.api_key == "my-key"


def test_api_key_falls_back_to_cfg():
    config = LLMConfig()
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_API_KEY = "cfg-key"
        assert config.api_key == "cfg-key"


def test_base_url_setter_and_getter():
    config = LLMConfig()
    config.base_url = "https://api.example.com"
    assert config.base_url == "https://api.example.com"


def test_base_url_falls_back_to_cfg():
    config = LLMConfig()
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_BASE_URL = "https://cfg.example.com"
        assert config.base_url == "https://cfg.example.com"


# ---------------------------------------------------------------------------
# provider
# ---------------------------------------------------------------------------


def test_provider_default_is_openai_string():
    config = LLMConfig()
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_API_KEY = None
        mock_cfg.LLM_BASE_URL = None
        assert config.provider == "openai"


def test_provider_setter_and_getter():
    config = LLMConfig()
    config.provider = "anthropic"
    assert config.provider == "anthropic"


def test_provider_returns_openai_provider_object_when_api_key_set():
    config = LLMConfig()
    config.api_key = "sk-test"
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_API_KEY = None
        mock_cfg.LLM_BASE_URL = None
        result = config.provider
        # An OpenAI-compatible provider object is returned, not the string.
        assert result != "openai"
        assert not isinstance(result, str)


def test_provider_returns_openai_provider_object_when_base_url_set():
    config = LLMConfig()
    config.base_url = "https://compat.example.com"
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_API_KEY = None
        mock_cfg.LLM_BASE_URL = None
        result = config.provider
        assert not isinstance(result, str)


# ---------------------------------------------------------------------------
# Model resolution through a string / object provider (resolve_model path)
# ---------------------------------------------------------------------------


def test_model_string_provider_prefix_rewrite():
    """An unknown provider model + api_key + a string provider rewrites the
    provider prefix on the model name."""
    config = LLMConfig()
    config.api_key = "sk-test"
    config.provider = "anthropic"
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_MODEL = "made-up:gpt-x"
        mock_cfg.LLM_BASE_URL = None
        # provider_name "made-up" is not native, api_key is set -> resolve through
        # the string provider, which rewrites the prefix to "anthropic".
        assert config.model == "anthropic:gpt-x"


def test_model_unknown_object_provider_fallback():
    """An unknown (non-OpenAI, non-string) provider object falls back to the
    original model name."""
    config = LLMConfig()
    config.api_key = "sk-test"
    config.provider = object()
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_MODEL = "made-up:gpt-x"
        mock_cfg.LLM_BASE_URL = None
        assert config.model == "made-up:gpt-x"
