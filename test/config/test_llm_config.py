from unittest import mock

import pytest
from zrb.config.config import CFG
from zrb.config.llm_config import LLMConfig, llm_config


def test_default_model_name_override():
    config = LLMConfig(default_model_name="test-model")
    assert config.default_model_name == "test-model"


def test_default_model_name_from_cfg(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MODEL", "cfg-model")
    config = LLMConfig()
    assert config.default_model_name == "cfg-model"


def test_default_model_name_none(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_MODEL", raising=False)
    config = LLMConfig()
    assert config.default_model_name is None


def test_default_model_base_url_override():
    config = LLMConfig(default_base_url="http://test.com")
    assert config.default_model_base_url == "http://test.com"


def test_default_model_base_url_from_cfg(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_BASE_URL", "http://cfg.com")
    config = LLMConfig()
    assert config.default_model_base_url == "http://cfg.com"


def test_default_model_base_url_none(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_BASE_URL", raising=False)
    config = LLMConfig()
    assert config.default_model_base_url is None


def test_default_model_api_key_override():
    config = LLMConfig(default_api_key="test-key")
    assert config.default_model_api_key == "test-key"


def test_default_model_api_key_from_cfg(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_API_KEY", "cfg-key")
    config = LLMConfig()
    assert config.default_model_api_key == "cfg-key"


def test_default_model_settings_override():
    mock_settings = mock.MagicMock()
    config = LLMConfig(default_model_settings=mock_settings)
    assert config.default_model_settings == mock_settings


def test_default_model_settings_none():
    config = LLMConfig()
    assert config.default_model_settings is None


def test_default_model_provider_override():
    mock_provider = mock.MagicMock()
    config = LLMConfig(default_model_provider=mock_provider)
    assert config.default_model_provider == mock_provider


def test_default_model_provider_openai_default(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("ZRB_LLM_API_KEY", raising=False)
    config = LLMConfig()
    assert config.default_model_provider == "openai"


@mock.patch("pydantic_ai.providers.openai.OpenAIProvider")
def test_default_model_provider_openai_custom(mock_provider, monkeypatch):
    monkeypatch.setenv("ZRB_LLM_BASE_URL", "http://custom.com")
    monkeypatch.setenv("ZRB_LLM_API_KEY", "custom-key")
    config = LLMConfig()
    provider = config.default_model_provider
    mock_provider.assert_called_with(
        base_url="http://custom.com", api_key="custom-key"
    )
    assert provider == mock_provider.return_value


def test_default_system_prompt_override():
    config = LLMConfig(default_system_prompt="test-prompt")
    assert config.default_system_prompt == "test-prompt"


def test_default_system_prompt_from_cfg(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_SYSTEM_PROMPT", "cfg-prompt")
    config = LLMConfig()
    assert config.default_system_prompt == "cfg-prompt"


def test_default_system_prompt_default():
    config = LLMConfig()
    assert isinstance(config.default_system_prompt, str)


def test_default_interactive_system_prompt_override():
    config = LLMConfig(default_interactive_system_prompt="test-prompt")
    assert config.default_interactive_system_prompt == "test-prompt"


def test_default_interactive_system_prompt_from_cfg(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_INTERACTIVE_SYSTEM_PROMPT", "cfg-prompt")
    config = LLMConfig()
    assert config.default_interactive_system_prompt == "cfg-prompt"


def test_default_interactive_system_prompt_default():
    config = LLMConfig()
    assert isinstance(config.default_interactive_system_prompt, str)


def test_default_persona_override():
    config = LLMConfig(default_persona="test-persona")
    assert config.default_persona == "test-persona"


def test_default_persona_from_cfg(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_PERSONA", "cfg-persona")
    config = LLMConfig()
    assert config.default_persona == "cfg-persona"


def test_default_persona_default():
    config = LLMConfig()
    assert isinstance(config.default_persona, str)


def test_default_special_instruction_prompt_override():
    config = LLMConfig(default_special_instruction_prompt="test-prompt")
    assert config.default_special_instruction_prompt == "test-prompt"


def test_default_special_instruction_prompt_from_cfg(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_SPECIAL_INSTRUCTION_PROMPT", "cfg-prompt")
    config = LLMConfig()
    assert config.default_special_instruction_prompt == "cfg-prompt"


def test_default_special_instruction_prompt_default():
    config = LLMConfig()
    assert isinstance(config.default_special_instruction_prompt, str)


def test_default_summarization_prompt_override():
    config = LLMConfig(default_summarization_prompt="test-prompt")
    assert config.default_summarization_prompt == "test-prompt"


def test_default_summarization_prompt_from_cfg(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_SUMMARIZATION_PROMPT", "cfg-prompt")
    config = LLMConfig()
    assert config.default_summarization_prompt == "cfg-prompt"


def test_default_summarization_prompt_default():
    config = LLMConfig()
    assert isinstance(config.default_summarization_prompt, str)


def test_default_context_enrichment_prompt_override():
    config = LLMConfig(default_context_enrichment_prompt="test-prompt")
    assert config.default_context_enrichment_prompt == "test-prompt"


def test_default_context_enrichment_prompt_from_cfg(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_CONTEXT_ENRICHMENT_PROMPT", "cfg-prompt")
    config = LLMConfig()
    assert config.default_context_enrichment_prompt == "cfg-prompt"


def test_default_context_enrichment_prompt_default():
    config = LLMConfig()
    assert isinstance(config.default_context_enrichment_prompt, str)


def test_default_model_override():
    mock_model = mock.MagicMock()
    config = LLMConfig(default_model=mock_model)
    assert config.default_model == mock_model


def test_default_model_none(monkeypatch):
    monkeypatch.delenv("ZRB_LLM_MODEL", raising=False)
    config = LLMConfig()
    assert config.default_model is None


@mock.patch("pydantic_ai.models.openai.OpenAIModel")
def test_default_model_from_name(mock_model, monkeypatch):
    monkeypatch.setenv("ZRB_LLM_MODEL", "gpt-4")
    config = LLMConfig()
    mock_provider = mock.MagicMock()
    config.set_default_model_provider(mock_provider)
    model = config.default_model
    assert model == mock_model.return_value
    mock_model.assert_called_with(
        model_name="gpt-4", provider=mock_provider
    )


def test_default_summarize_history_override():
    config = LLMConfig(default_summarize_history=False)
    assert not config.default_summarize_history


def test_default_summarize_history_from_cfg(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_SUMMARIZE_HISTORY", "false")
    config = LLMConfig()
    assert not config.default_summarize_history


def test_default_history_summarization_token_threshold_override():
    config = LLMConfig(default_history_summarization_token_threshold=100)
    assert config.default_history_summarization_token_threshold == 100


def test_default_history_summarization_token_threshold_from_cfg(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_HISTORY_SUMMARIZATION_TOKEN_THRESHOLD", "200")
    config = LLMConfig()
    assert config.default_history_summarization_token_threshold == 200


def test_default_enrich_context_override():
    config = LLMConfig(default_enrich_context=False)
    assert not config.default_enrich_context


def test_default_enrich_context_from_cfg(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_ENRICH_CONTEXT", "false")
    config = LLMConfig()
    assert not config.default_enrich_context


def test_default_context_enrichment_token_threshold_override():
    config = LLMConfig(default_context_enrichment_token_threshold=100)
    assert config.default_context_enrichment_token_threshold == 100


def test_default_context_enrichment_token_threshold_from_cfg(monkeypatch):
    monkeypatch.setenv("ZRB_LLM_CONTEXT_ENRICHMENT_TOKEN_THRESHOLD", "200")
    config = LLMConfig()
    assert config.default_context_enrichment_token_threshold == 200


def test_setters():
    config = LLMConfig()
    config.set_default_persona("new-persona")
    assert config.default_persona == "new-persona"

    config.set_default_system_prompt("new-system-prompt")
    assert config.default_system_prompt == "new-system-prompt"

    config.set_default_interactive_system_prompt("new-interactive-prompt")
    assert config.default_interactive_system_prompt == "new-interactive-prompt"

    config.set_default_special_instruction_prompt("new-special-prompt")
    assert config.default_special_instruction_prompt == "new-special-prompt"

    config.set_default_summarization_prompt("new-summarization-prompt")
    assert config.default_summarization_prompt == "new-summarization-prompt"

    config.set_default_context_enrichment_prompt("new-context-prompt")
    assert config.default_context_enrichment_prompt == "new-context-prompt"

    config.set_default_model_name("new-model-name")
    assert config.default_model_name == "new-model-name"

    config.set_default_model_api_key("new-api-key")
    assert config.default_model_api_key == "new-api-key"

    config.set_default_model_base_url("http://new.com")
    assert config.default_model_base_url == "http://new.com"

    mock_provider = mock.MagicMock()
    config.set_default_model_provider(mock_provider)
    assert config.default_model_provider == mock_provider

    mock_model = mock.MagicMock()
    config.set_default_model(mock_model)
    assert config.default_model == mock_model

    config.set_default_summarize_history(False)
    assert not config.default_summarize_history

    config.set_default_history_summarization_token_threshold(500)
    assert config.default_history_summarization_token_threshold == 500

    config.set_default_enrich_context(False)
    assert not config.default_enrich_context

    config.set_default_context_enrichment_token_threshold(600)
    assert config.default_context_enrichment_token_threshold == 600

    mock_settings = mock.MagicMock()
    config.set_default_model_settings(mock_settings)
    assert config.default_model_settings == mock_settings


def test_global_llm_config_instance():
    assert isinstance(llm_config, LLMConfig)
