import pytest

from zrb.llm.agent.summarizer import create_summarizer_agent


def test_create_summarizer_agent_defaults():
    agent = create_summarizer_agent()
    assert agent is not None


def test_create_summarizer_agent_custom():
    agent = create_summarizer_agent(system_prompt="Custom prompt")
    assert agent is not None
