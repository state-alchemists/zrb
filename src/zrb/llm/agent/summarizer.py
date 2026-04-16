from typing import TYPE_CHECKING, Callable

from zrb.llm.agent.common import create_agent
from zrb.llm.config.config import llm_config as default_llm_config
from zrb.llm.prompt.prompt import (
    get_conversational_summarizer_system_prompt,
    get_message_summarizer_system_prompt,
    get_summarizer_system_prompt,
)

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.models import Model


def create_summarizer_agent(
    model: "str | None | Model" = None,
    system_prompt: str | None = None,
    model_getter: "Callable[[str | Model | None], str | Model | None] | None" = None,
    model_renderer: "Callable[[str | Model | None], str | Model | None] | None" = None,
) -> "Agent[None, str]":
    effective_system_prompt = system_prompt or get_summarizer_system_prompt()
    if model is None:
        model = default_llm_config.small_model
    effective_getter = model_getter or default_llm_config.model_getter
    effective_renderer = model_renderer or default_llm_config.model_renderer
    if effective_getter:
        model = effective_getter(model)
    if effective_renderer:
        model = effective_renderer(model)
    return create_agent(
        model=model,
        system_prompt=effective_system_prompt,
    )


def create_conversational_summarizer_agent(
    model: "str | None | Model" = None,
    system_prompt: str | None = None,
    model_getter: "Callable[[str | Model | None], str | Model | None] | None" = None,
    model_renderer: "Callable[[str | Model | None], str | Model | None] | None" = None,
) -> "Agent[None, str]":
    effective_system_prompt = (
        system_prompt or get_conversational_summarizer_system_prompt()
    )
    return create_summarizer_agent(
        model=model,
        system_prompt=effective_system_prompt,
        model_getter=model_getter,
        model_renderer=model_renderer,
    )


def create_message_summarizer_agent(
    model: "str | None | Model" = None,
    system_prompt: str | None = None,
    model_getter: "Callable[[str | Model | None], str | Model | None] | None" = None,
    model_renderer: "Callable[[str | Model | None], str | Model | None] | None" = None,
) -> "Agent[None, str]":
    effective_system_prompt = system_prompt or get_message_summarizer_system_prompt()
    return create_summarizer_agent(
        model=model,
        system_prompt=effective_system_prompt,
        model_getter=model_getter,
        model_renderer=model_renderer,
    )
