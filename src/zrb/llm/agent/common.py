from __future__ import annotations

from typing import TYPE_CHECKING, Any

from zrb.llm.config.config import llm_config as default_llm_config
from zrb.llm.util.prompt import expand_prompt

if TYPE_CHECKING:
    from pydantic_ai import (
        Agent,
        Tool,
    )
    from pydantic_ai._agent_graph import HistoryProcessor
    from pydantic_ai.models import Model
    from pydantic_ai.output import OutputDataT, OutputSpec
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset


def create_agent(
    model: "Model | str | None" = None,
    system_prompt: str = "",
    tools: list["Tool | ToolFuncEither"] = [],
    toolsets: list["AbstractToolset[None]"] = [],
    model_settings: "ModelSettings | None" = None,
    history_processors: list["HistoryProcessor"] | None = None,
    output_type: "OutputSpec[OutputDataT]" = str,
    retries: int = 1,
    yolo: bool = False,
) -> "Agent[None, Any]":
    from pydantic_ai import Agent, DeferredToolRequests
    from pydantic_ai.toolsets import FunctionToolset

    # Expand system prompt with references
    effective_system_prompt = expand_prompt(system_prompt)

    final_output_type = output_type
    effective_toolsets = list(toolsets)
    if tools:
        effective_toolsets.append(FunctionToolset(tools=tools))

    if not yolo:
        final_output_type = output_type | DeferredToolRequests
        effective_toolsets = [ts.approval_required() for ts in effective_toolsets]

    if model is None:
        model = default_llm_config.model

    return Agent(
        model=model,
        output_type=final_output_type,
        instructions=effective_system_prompt,
        toolsets=effective_toolsets,
        model_settings=model_settings,
        history_processors=history_processors,
        retries=retries,
    )
