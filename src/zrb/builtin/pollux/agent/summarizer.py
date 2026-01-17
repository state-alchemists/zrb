from typing import TYPE_CHECKING

from zrb.builtin.pollux.agent.agent import create_agent
from zrb.builtin.pollux.config.config import LLMConfig
from zrb.builtin.pollux.config.config import llm_config as default_llm_config
from zrb.builtin.pollux.prompt.default import get_default_prompt

if TYPE_CHECKING:
    from pydantic_ai import Agent


def create_summarizer_agent(
    model: str | None = None,
    llm_config: LLMConfig | None = None,
) -> "Agent[None, str]":
    config = llm_config or default_llm_config
    agent_model = model or config.model
    system_prompt = get_default_prompt("summarizer")

    return create_agent(
        model=agent_model,
        system_prompt=system_prompt,
    )
