from typing import TYPE_CHECKING

from zrb.llm.agent.common import create_agent
from zrb.llm.config.config import llm_config as default_llm_config
from zrb.llm.prompt.prompt import get_prompt

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.models import Model


def create_summarizer_agent(
    model: "str | None | Model" = None,
    system_prompt: str | None = None,
) -> "Agent[None, str]":
    effective_system_prompt = system_prompt or get_prompt("conversational_summarizer")
    if model is None:
        model = default_llm_config.small_model
    final_model = default_llm_config.resolve_model(model)
    return create_agent(
        model=final_model,
        system_prompt=effective_system_prompt,
    )


def create_conversational_summarizer_agent(
    model: "str | None | Model" = None,
    system_prompt: str | None = None,
) -> "Agent[None, str]":
    effective_system_prompt = system_prompt or get_prompt("conversational_summarizer")
    return create_summarizer_agent(
        model=model,
        system_prompt=effective_system_prompt,
    )


def create_message_summarizer_agent(
    model: "str | None | Model" = None,
    system_prompt: str | None = None,
) -> "Agent[None, str]":
    effective_system_prompt = system_prompt or get_prompt("message_summarizer")
    return create_summarizer_agent(
        model=model,
        system_prompt=effective_system_prompt,
    )
