from __future__ import annotations

import copy
import inspect
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any

from zrb.config.config import CFG
from zrb.llm.config.config import llm_config as default_llm_config
from zrb.llm.util.prompt import expand_prompt
from zrb.util.string.conversion import to_string

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from pydantic_ai import (
        Agent,
        Tool,
    )
    from pydantic_ai.capabilities import AbstractCapability
    from pydantic_ai.messages import ModelMessage
    from pydantic_ai.models import Model
    from pydantic_ai.output import OutputDataT, OutputSpec
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.tools import ToolFuncEither
    from pydantic_ai.toolsets import AbstractToolset

    # zrb applies history processors itself in runner._apply_history_processors
    # (passing extra positional args like `reserved_tokens` in some call sites),
    # so the contract is broader than pydantic-ai's `HistoryProcessor` type alias.
    # Kept local to avoid depending on a private pydantic-ai symbol.
    HistoryProcessor = Callable[..., Awaitable[list[ModelMessage]]]


def _wrap_tool(tool: "Tool | ToolFuncEither") -> "Tool | ToolFuncEither":
    """Wrap a tool with error handling to prevent crashes."""
    if hasattr(tool, "function"):
        from pydantic_ai import Tool as PydanticTool

        # It is a Tool instance
        original_func = tool.function
        safe_func = create_safe_wrapper(original_func)
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
        return create_safe_wrapper(tool)


def safe_copy_result(result: Any) -> Any:
    """Create a safe copy of a tool result to prevent mutation.

    Deep copies mutable objects (lists, dicts, sets) but returns immutable
    objects (strings, numbers, None) as-is. This prevents pydantic-ai from
    modifying the original tool results during processing.
    """
    if result is None:
        return None
    if isinstance(result, (str, int, float, bool)):
        return result
    if isinstance(result, (list, dict, set)):
        return copy.deepcopy(result)
    # For other types (including tuples which may contain mutable elements),
    # perform a deep copy to be safe
    try:
        return copy.deepcopy(result)
    except Exception:
        # If deepcopy fails (e.g., for complex objects), return as-is
        # This maintains backward compatibility while fixing the common cases
        return result


def create_safe_wrapper(func: Callable) -> Callable:
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

            # Create a safe copy to prevent mutation by pydantic-ai
            safe_result = safe_copy_result(result)

            # Otherwise wrap successful result in ToolReturn
            return ToolReturn(
                return_value=safe_result, content=to_string(safe_result), metadata={}
            )
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
                result = await super().call_tool(name, tool_args, ctx, tool)
                # If result is already a ToolReturn, return it as-is
                if isinstance(result, ToolReturn):
                    return result
                # Create a safe copy to prevent mutation by pydantic-ai
                safe_result = safe_copy_result(result)
                return ToolReturn(
                    return_value=safe_result,
                    content=to_string(safe_result),
                    metadata={},
                )
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
    capabilities: "list[AbstractCapability[Any]] | None" = None,
    output_type: "OutputSpec[OutputDataT]" = str,
    retries: int | None = None,
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
        effective_toolsets.append(
            FunctionToolset(tools=safe_tools, max_retries=CFG.LLM_TOOL_MAX_RETRIES)
        )

    if yolo is not True:
        final_output_type = output_type | DeferredToolRequests

        if callable(yolo):

            def check_approval(ctx: Any, tool_def: Any, args: dict[str, Any]) -> bool:
                return not yolo(tool_def)

            effective_toolsets = [
                ts.approval_required(check_approval) for ts in effective_toolsets
            ]
        else:
            effective_toolsets = [ts.approval_required() for ts in effective_toolsets]

    if model is None:
        model = default_llm_config.model

    final_model = default_llm_config.resolve_model(model)
    effective_retries = retries if retries is not None else CFG.LLM_TOOL_MAX_RETRIES
    effective_model_settings = _apply_capability_constraints(
        model, final_model, model_settings
    )

    agent = Agent(
        model=final_model,
        output_type=final_output_type,
        instructions=effective_system_prompt,
        toolsets=effective_toolsets,
        model_settings=effective_model_settings,
        # history_processors intentionally omitted: pydantic-ai applies them on a
        # shallow copy of message_history without writing back, so any summarization
        # it does is immediately discarded. We apply them ourselves in _prepare_history
        # (before the first model call) and in _execution_loop (between tool-call
        # iterations) where we own the history reference.
        capabilities=capabilities or [],
        retries={"tools": effective_retries},
    )
    agent._zrb_history_processors = history_processors or []  # type: ignore[attr-defined]
    return agent


def _apply_capability_constraints(
    model: "Model | str | None",
    final_model: "Model | str | None",
    model_settings: "ModelSettings | None",
) -> "ModelSettings | None":
    """Translate :mod:`zrb.llm.util.capabilities` into pydantic-ai settings.

    Currently the only constraint applied here is
    ``supports_parallel_tool_calls=False`` → ``parallel_tool_calls=False``
    in the provider request. Caller-supplied settings always win — if
    ``parallel_tool_calls`` is already set, this helper leaves it alone.

    .. note::

       This is **defense-in-depth, not the primary fix** for models that
       malform parallel tool calls. Real OpenAI / Azure OpenAI honor the
       flag; Ollama-cloud's OpenAI-compatible endpoint silently ignores
       it (verified empirically against minimax-m2.7 and glm-4.7). The
       **prompt-side** parallel-tool-call section in the Tool Usage Guide
       (see :func:`zrb.llm.prompt.tool_guidance.get_parallel_tool_call_section`)
       is what actually changes those models' behavior. Both layers use
       the same capability registry, so toggling
       ``supports_parallel_tool_calls`` in one place updates both.
    """
    from zrb.llm.util.capabilities import model_capabilities

    capabilities = model_capabilities.get(
        model if isinstance(model, str) else final_model
    )
    if capabilities.supports_parallel_tool_calls is not False:
        return model_settings
    if model_settings is None:
        return {"parallel_tool_calls": False}
    if "parallel_tool_calls" in model_settings:
        return model_settings
    return {**model_settings, "parallel_tool_calls": False}
