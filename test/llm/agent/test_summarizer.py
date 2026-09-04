import pytest

from zrb.llm.agent.summarizer import (
    create_message_summarizer_agent,
    create_summarizer_agent,
)


def test_create_summarizer_agent_defaults():
    agent = create_summarizer_agent()
    assert agent is not None


def test_create_summarizer_agent_custom():
    agent = create_summarizer_agent(system_prompt="Custom prompt")
    assert agent is not None


def test_summarizer_agent_follows_the_run_small_model_override(monkeypatch):
    """`/model small <name>` must reach the summarizer — its main consumer.

    The history processor calls `create_message_summarizer_agent()` with no
    model argument, so the override has to be picked up inside
    `resolve_configured_small_model` rather than passed in by each call site.
    Asserted at the `create_agent` boundary so no provider client is built.
    """
    import zrb.llm.agent.summarizer as summarizer
    from zrb.config.config import CFG
    from zrb.llm.agent_state import current_small_model

    seen = {}

    def fake_create_agent(*args, **kwargs):
        seen.update(kwargs)
        return object()

    monkeypatch.setattr(summarizer, "create_agent", fake_create_agent)
    monkeypatch.setattr(CFG, "LLM_SMALL_MODEL", "openai:gpt-4o-mini")
    monkeypatch.setattr(CFG, "LLM_API_KEY", None)
    monkeypatch.setattr(CFG, "LLM_BASE_URL", None)
    monkeypatch.setattr(CFG, "LLM_PROVIDER", None)
    token = current_small_model.set("deepseek:deepseek-chat")
    try:
        create_message_summarizer_agent()
    finally:
        current_small_model.reset(token)

    assert seen["model"] == "deepseek:deepseek-chat"


def test_summarizer_agent_uses_cfg_small_model_when_no_override(monkeypatch):
    """Without a `/model small`, static config still wins."""
    import zrb.llm.agent.summarizer as summarizer
    from zrb.config.config import CFG

    seen = {}
    monkeypatch.setattr(
        summarizer, "create_agent", lambda *a, **k: seen.update(k) or object()
    )
    monkeypatch.setattr(CFG, "LLM_SMALL_MODEL", "openai:gpt-4o-mini")
    monkeypatch.setattr(CFG, "LLM_API_KEY", None)
    monkeypatch.setattr(CFG, "LLM_BASE_URL", None)
    monkeypatch.setattr(CFG, "LLM_PROVIDER", None)

    create_message_summarizer_agent()

    assert seen["model"] == "openai:gpt-4o-mini"
