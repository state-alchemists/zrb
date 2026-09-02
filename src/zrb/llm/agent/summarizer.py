from typing import TYPE_CHECKING

from zrb.llm.agent.common import create_agent
from zrb.llm.config.model_resolver import resolve_configured_small_model
from zrb.llm.prompt.prompt import get_prompt

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.models import Model


def create_summarizer_agent(
    model: "str | None | Model" = None,
    system_prompt: str | None = None,
) -> "Agent[None, str]":
    effective_system_prompt = system_prompt or get_prompt("conversational_summarizer")
    final_model = resolve_configured_small_model(model)
    # Already resolved here; resolve_model=False avoids resolving twice
    # inside create_agent.
    return create_agent(
        model=final_model,
        system_prompt=effective_system_prompt,
        resolve_model=False,
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
