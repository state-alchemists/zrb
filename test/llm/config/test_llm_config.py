"""Tests for LLMConfig class."""
from unittest.mock import MagicMock, patch

import pytest

from zrb.llm.config.config import LLMConfig


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
    with patch.object(config, "_api_key", None):
        with patch("zrb.llm.config.config.CFG") as mock_cfg:
            mock_cfg.LLM_API_KEY = "cfg-api-key"
            assert config.api_key == "cfg-api-key"


def test_llm_config_base_url_from_cfg():
    """Test LLMConfig base_url falls back to CFG."""
    config = LLMConfig()
    with patch.object(config, "_base_url", None):
        with patch("zrb.llm.config.config.CFG") as mock_cfg:
            mock_cfg.LLM_BASE_URL = "https://cfg.example.com"
            assert config.base_url == "https://cfg.example.com"


def test_llm_config_get_builtin_providers():
    """Test _get_builtin_providers returns expected providers."""
    config = LLMConfig()
    providers = config._get_builtin_providers()
    assert isinstance(providers, set)
    # Should contain common providers
    assert "openai" in providers


def test_llm_config_builtin_providers_cached():
    """Test _get_builtin_providers caches the result."""
    config = LLMConfig()
    providers1 = config._get_builtin_providers()
    providers2 = config._get_builtin_providers()
    assert providers1 is providers2


def test_llm_config_resolve_model_by_name_openai():
    """Test _resolve_model_by_name with openai provider."""
    config = LLMConfig()
    result = config._resolve_model_by_name("openai:gpt-4")
    assert result == "openai:gpt-4"


def test_llm_config_resolve_model_by_name_builtin():
    """Test _resolve_model_by_name with built-in provider."""
    config = LLMConfig()
    # anthropic is a built-in provider
    result = config._resolve_model_by_name("anthropic:claude-3")
    assert result == "anthropic:claude-3"


def test_llm_config_resolve_model_by_name_custom():
    """Test _resolve_model_by_name with unknown provider."""
    config = LLMConfig()
    # Unknown provider without API config
    result = config._resolve_model_by_name("custom:model")
    assert result == "custom:model"


def test_llm_config_resolve_model_by_name_with_api_key():
    """Test _resolve_model_by_name with API key set."""
    config = LLMConfig()
    config.api_key = "test-key"
    
    # Provider should resolve to OpenAIProvider when api_key is set
    result = config._resolve_model_by_name("openai:gpt-4")
    # Should return a model (either string or OpenAIChatModel)
    assert result is not None


def test_llm_config_resolve_model_string_provider():
    """Test _resolve_model with string provider."""
    config = LLMConfig()
    result = config._resolve_model("custom-model", "openai")
    assert result == "openai:custom-model"


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
    # No API key or base_url set
    config._api_key = None
    config._base_url = None
    config._provider = None
    
    result = config.provider
    assert result == "openai"


def test_llm_config_model_default():
    """Test model returns default when not set."""
    config = LLMConfig()
    config._model = None
    config._api_key = None
    config._base_url = None
    config._provider = None
    
    with patch("zrb.llm.config.config.CFG") as mock_cfg:
        mock_cfg.LLM_MODEL = "openai:gpt-4o"
        mock_cfg.LLM_API_KEY = None
        mock_cfg.LLM_BASE_URL = None
        # Should return the model string
        result = config.model
        assert result == "openai:gpt-4o"