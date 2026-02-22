from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
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


def _wrap_tool(tool: "Tool | ToolFuncEither") -> "Tool | ToolFuncEither":
    """Wrap a tool with error handling to prevent crashes."""
    if hasattr(tool, "function"):
        from pydantic_ai import Tool as PydanticTool

        # It is a Tool instance
        original_func = tool.function
        safe_func = _create_safe_wrapper(original_func)
        if isinstance(tool, PydanticTool):
            return PydanticTool(
                safe_func,
                name=tool.name,
                description=tool.description,
                takes_ctx=tool.takes_ctx,
                max_retries=tool.max_retries,
                docstring_format=tool.docstring_format,
                require_parameter_descriptions=tool.require_parameter_descriptions,
                strict=tool.strict,
                sequential=tool.sequential,
                requires_approval=tool.requires_approval,
                timeout=tool.timeout,
            )
        return tool
    else:
        # It is a callable
        return _create_safe_wrapper(tool)


def _create_safe_wrapper(func: Callable) -> Callable:
    """Create a wrapper that catches exceptions and returns ToolReturn objects."""
    from pydantic_ai import ToolReturn

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # If result is already a ToolReturn, return it as-is
            if isinstance(result, ToolReturn):
                return result

            # Otherwise wrap successful result in ToolReturn
            return ToolReturn(return_value=result, content=result, metadata={})
        except Exception as e:
            error_msg = f"Error executing tool {func.__name__}: {e}"
            return ToolReturn(
                return_value=None, content=error_msg, metadata={"error": True}
            )

    return wrapper


def _wrap_toolset(toolset: "AbstractToolset[None]") -> "AbstractToolset[None]":
    """Wrap a toolset with error handling."""
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import WrapperToolset

    class SafeToolsetWrapper(WrapperToolset):
        async def call_tool(
            self, name: str, tool_args: dict[str, Any], ctx: Any, tool: Any
        ) -> Any:
            try:
                return await super().call_tool(name, tool_args, ctx, tool)
            except Exception as e:
                error_msg = f"Error executing tool {name}: {e}"
                return ToolReturn(
                    return_value=None, content=error_msg, metadata={"error": True}
                )

    return SafeToolsetWrapper(toolset)


def create_agent(
    model: "Model | str | None" = None,
    system_prompt: str = "",
    tools: list["Tool | ToolFuncEither"] = [],
    toolsets: list["AbstractToolset[None]"] = [],
    model_settings: "ModelSettings | None" = None,
    history_processors: list["HistoryProcessor"] | None = None,
    output_type: "OutputSpec[OutputDataT]" = str,
    retries: int = 1,
    yolo: bool | Callable[[Any, Any, dict[str, Any]], bool] = False,
) -> "Agent[None, Any]":
    from pydantic_ai import Agent, DeferredToolRequests
    from pydantic_ai.toolsets import FunctionToolset

    # Expand system prompt with references
    effective_system_prompt = expand_prompt(system_prompt)

    # Wrap tools and toolsets with error handling
    safe_tools = [_wrap_tool(t) for t in tools]
    safe_toolsets = [_wrap_toolset(t) for t in toolsets]

    final_output_type = output_type
    effective_toolsets = list(safe_toolsets)
    if safe_tools:
        effective_toolsets.append(FunctionToolset(tools=safe_tools))

    if yolo is not True:
        final_output_type = output_type | DeferredToolRequests

        if callable(yolo):

            def check_approval(ctx: Any, tool_def: Any, args: dict[str, Any]) -> bool:
                try:
                    return not yolo(ctx, tool_def, args)
                except TypeError:
                    return not yolo(ctx)

            effective_toolsets = [
                ts.approval_required(check_approval) for ts in effective_toolsets
            ]
        else:
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
