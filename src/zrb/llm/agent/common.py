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
        # lazy: heavy third-party
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


def _permission_gate(tool_name: str, capability: Any, args: dict[str, Any]) -> Any:
    """Return a blocked ``ToolReturn`` if the in-force policy denies this call.

    Returns ``None`` when nothing denies it (the default — no policy and
    ``AgentMode.DEFAULT`` → always ``None``, so the synchronous path is
    unchanged). Enforces the *deny* outcome that the approval layer (allow/ask)
    cannot express, without touching the deferred-request machinery.
    """
    # lazy: circular — common is imported by the runner; permission is a leaf,
    # but keep the read local so the policy is re-resolved per call.
    from pydantic_ai import ToolReturn

    from zrb.llm.permission import DENY, get_current_agent_mode, get_effective_policy

    policy = get_effective_policy()
    if policy is None:
        return None
    if policy.decide(tool_name, capability, args) != DENY:
        return None
    mode = get_current_agent_mode().value
    return ToolReturn(
        return_value=None,
        content=(
            f"Blocked: '{tool_name}' is not permitted under the current "
            f"permission policy (mode: {mode}). "
            "[SYSTEM SUGGESTION]: this is a read-only / restricted context. "
            "Finish discovery, then call ExitPlanMode (if in plan mode) to "
            "present your plan for approval before making changes."
        ),
        metadata={"blocked": True},
    )


def _truncated_content(content: str) -> tuple[str, dict[str, Any]]:
    """Apply the global tool-result size backstop to a model-facing string.

    Returns ``(content, metadata)``. The cap (``CFG.LLM_MAX_TOOL_RESULT_CHARS``)
    is high enough that typical output is untouched; ``0`` disables it. Only the
    text shown to the model is affected — never a tool's structured return value.
    """
    # lazy: circular — common → truncate is fine, but keep CFG read local so
    # the cap is re-read per call (tests may patch it) and import stays cheap.
    from zrb.llm.agent.truncate import truncate_tool_content

    truncated, was_truncated = truncate_tool_content(
        content, limit=CFG.LLM_MAX_TOOL_RESULT_CHARS
    )
    if not was_truncated:
        return content, {}
    return truncated, {"truncated": True, "original_chars": len(content)}


def create_safe_wrapper(func: Callable) -> Callable:
    """Create a wrapper that catches exceptions and returns ToolReturn objects."""
    # lazy: heavy third-party
    from pydantic_ai import ToolReturn

    # lazy: circular — permission is a leaf module; capability is read at wrap
    # time (cheap) so the per-call gate need not re-import it.
    from zrb.llm.permission import tool_capability

    capability = tool_capability(func)

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            blocked = _permission_gate(func.__name__, capability, kwargs)
            if blocked is not None:
                return blocked

            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # If result is already a ToolReturn, return it as-is. The tool framed
            # its own content (possibly truncated deliberately) — respect it.
            if isinstance(result, ToolReturn):
                return result

            # Create a safe copy to prevent mutation by pydantic-ai
            safe_result = safe_copy_result(result)

            # Otherwise wrap successful result in ToolReturn, applying the global
            # content-size backstop (return_value is left whole).
            content, metadata = _truncated_content(to_string(safe_result))
            return ToolReturn(
                return_value=safe_result, content=content, metadata=metadata
            )
        except Exception as e:
            error_msg = f"Error executing tool {func.__name__}: {e}"
            return ToolReturn(
                return_value=None, content=error_msg, metadata={"error": True}
            )

    return wrapper


def _wrap_toolset(toolset: "AbstractToolset[None]") -> "AbstractToolset[None]":
    """Wrap a toolset with error handling."""
    # lazy: heavy third-party
    from pydantic_ai import ToolReturn
    from pydantic_ai.toolsets import WrapperToolset

    # lazy: circular — permission is a leaf module.
    from zrb.llm.permission import tool_capability

    class SafeToolsetWrapper(WrapperToolset):
        async def call_tool(
            self, name: str, tool_args: dict[str, Any], ctx: Any, tool: Any
        ) -> Any:
            try:
                blocked = _permission_gate(
                    name, tool_capability(tool), tool_args or {}
                )
                if blocked is not None:
                    return blocked
                result = await super().call_tool(name, tool_args, ctx, tool)
                # If result is already a ToolReturn, return it as-is
                if isinstance(result, ToolReturn):
                    return result
                # Create a safe copy to prevent mutation by pydantic-ai
                safe_result = safe_copy_result(result)
                content, metadata = _truncated_content(to_string(safe_result))
                return ToolReturn(
                    return_value=safe_result,
                    content=content,
                    metadata=metadata,
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
    # lazy: heavy third-party
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
    # lazy: zrb internal (heavy via transitive / circular)
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
