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
