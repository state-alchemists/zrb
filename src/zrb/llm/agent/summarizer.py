from typing import TYPE_CHECKING

from zrb.llm.agent.common import create_agent
from zrb.llm.prompt.prompt import get_summarizer_system_prompt

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.models import Model


def create_summarizer_agent(
    model: "str | None | Model" = None,
    system_prompt: str | None = None,
) -> "Agent[None, str]":
    effective_system_prompt = system_prompt or get_summarizer_system_prompt()

    return create_agent(
        model=model,
        system_prompt=effective_system_prompt,
    )
