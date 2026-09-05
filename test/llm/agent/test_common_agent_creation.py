"""Tests for agent common utilities."""

from unittest.mock import MagicMock, patch

from zrb.config.config import CFG
from zrb.llm.agent.common import create_agent


def _settings_of(mock_agent_class) -> dict:
    _, kwargs = mock_agent_class.call_args
    return kwargs.get("model_settings")


def _default_timeout() -> float:
    """The request deadline every agent carries, in seconds."""
    return CFG.LLM_REQUEST_TIMEOUT / 1000


def _reasoning_defaults() -> dict:
    """The reasoning/caching defaults every agent carries unless overridden."""
    return {
        "openai_reasoning_summary": "auto",
        "openai_prompt_cache_retention": "24h",
        "anthropic_cache": "5m",
    }


def test_create_agent_leaves_unknown_models_unchanged():
    """A model with no capability entry gets no *capability* injection.

    The request deadline is not a capability constraint — it applies to every
    model — so it is present here while ``parallel_tool_calls`` is not.
    """
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(model="openai:gpt-4o", system_prompt="test", yolo=True)

    settings = _settings_of(mock_agent_class)
    assert "parallel_tool_calls" not in settings
    assert settings == {"timeout": _default_timeout(), **_reasoning_defaults()}


def test_create_agent_applies_the_configured_request_timeout(monkeypatch):
    monkeypatch.setattr(CFG, "DEFAULT_LLM_REQUEST_TIMEOUT", "45000")
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_REQUEST_TIMEOUT", raising=False)
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(model="openai:gpt-4o", system_prompt="test", yolo=True)

    assert _settings_of(mock_agent_class) == {"timeout": 45.0, **_reasoning_defaults()}


def test_create_agent_lets_the_caller_own_the_timeout():
    """An explicit ``timeout`` is never overwritten by the configured default."""
    from zrb.llm.agent.common import create_agent

    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="openai:gpt-4o",
            system_prompt="test",
            model_settings={"timeout": 5.0},
            yolo=True,
        )

    assert _settings_of(mock_agent_class) == {"timeout": 5.0, **_reasoning_defaults()}


def test_create_agent_lets_the_caller_own_reasoning_defaults():
    """Caller-supplied openai_reasoning_summary/prompt_cache_retention win."""
    from pydantic_ai.models.openai import OpenAIResponsesModelSettings

    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="openai:gpt-4o",
            system_prompt="test",
            model_settings=OpenAIResponsesModelSettings(
                openai_reasoning_summary="detailed"
            ),
            yolo=True,
        )

    settings = _settings_of(mock_agent_class)
    assert settings["openai_reasoning_summary"] == "detailed"
    assert settings["openai_prompt_cache_retention"] == "24h"


def test_create_agent_lets_the_caller_own_anthropic_cache():
    from pydantic_ai.models.anthropic import AnthropicModelSettings

    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="anthropic:claude-sonnet-4-5",
            system_prompt="test",
            model_settings=AnthropicModelSettings(anthropic_cache="1h"),
            yolo=True,
        )

    settings = _settings_of(mock_agent_class)
    assert settings["anthropic_cache"] == "1h"
    assert settings["openai_reasoning_summary"] == "auto"


def test_create_agent_applies_configured_thinking_level(monkeypatch):
    """CFG.LLM_THINKING maps onto pydantic-ai's unified `thinking` setting."""
    monkeypatch.setattr(CFG, "DEFAULT_LLM_THINKING", "high")
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_THINKING", raising=False)
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(model="openai:gpt-4o", system_prompt="test", yolo=True)

    assert _settings_of(mock_agent_class)["thinking"] == "high"


def test_create_agent_omits_thinking_when_unset(monkeypatch):
    """LLM_THINKING unset (the default) leaves `thinking` out entirely, so
    each provider's own default behavior applies untouched."""
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_THINKING", raising=False)
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(model="openai:gpt-4o", system_prompt="test", yolo=True)

    assert "thinking" not in _settings_of(mock_agent_class)


def test_create_agent_defaults_thinking_true_for_gemini_2_5_and_3(monkeypatch):
    """Gemini 2.5/3 bill `thoughts_tokens` unconditionally but only return a
    readable summary when `thinking` is set — default it on for just this
    model family so the summary is visible without a manual LLM_THINKING."""
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_THINKING", raising=False)
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="google-gla:gemini-2.5-flash", system_prompt="test", yolo=True
        )

    assert _settings_of(mock_agent_class)["thinking"] is True


def test_create_agent_omits_thinking_default_for_non_thinking_gemini(monkeypatch):
    """Gemini 2.0 and earlier don't get the `thinking=True` nudge — they
    aren't in the `supports_thinking_summary` capability list."""
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_THINKING", raising=False)
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="google-gla:gemini-2.0-flash", system_prompt="test", yolo=True
        )

    assert "thinking" not in _settings_of(mock_agent_class)


def test_create_agent_configured_thinking_level_wins_over_gemini_default(
    monkeypatch,
):
    """An explicit LLM_THINKING level always wins over the Gemini `True` default."""
    monkeypatch.setattr(CFG, "DEFAULT_LLM_THINKING", "high")
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_THINKING", raising=False)
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="google-gla:gemini-2.5-flash", system_prompt="test", yolo=True
        )

    assert _settings_of(mock_agent_class)["thinking"] == "high"


def test_create_agent_lets_the_caller_own_thinking_for_gemini(monkeypatch):
    """Caller-supplied `thinking` wins over the Gemini `True` default."""
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_THINKING", raising=False)
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(
            model="google-gla:gemini-2.5-flash",
            system_prompt="test",
            model_settings={"thinking": False},
            yolo=True,
        )

    assert _settings_of(mock_agent_class)["thinking"] is False


def test_create_agent_omits_the_timeout_when_disabled(monkeypatch):
    """A non-positive timeout means "no deadline", not "expire immediately"."""
    monkeypatch.setattr(CFG, "DEFAULT_LLM_REQUEST_TIMEOUT", "0")
    monkeypatch.delenv(f"{CFG.ENV_PREFIX}_LLM_REQUEST_TIMEOUT", raising=False)
    mock_agent_class = MagicMock()
    with patch("pydantic_ai.Agent", mock_agent_class):
        create_agent(model="openai:gpt-4o", system_prompt="test", yolo=True)

    # No timeout key, but the reasoning/caching defaults still apply — those
    # are unconditional, unlike the timeout which can be disabled.
    assert _settings_of(mock_agent_class) == _reasoning_defaults()
