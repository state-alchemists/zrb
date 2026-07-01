from __future__ import annotations

import copy
import inspect
import json
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, cast

from zrb.config.config import CFG
from zrb.llm.agent.gates import permission_gate, sandbox_gate
from zrb.llm.agent.run.hook_result_extractor import (
    extract_post_tool_decision,
    extract_pre_tool_decision,
)
from zrb.llm.config.config import llm_config as default_llm_config
from zrb.llm.hook.manager import hook_manager
from zrb.llm.hook.types import HookEvent
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

    # zrb applies history processors itself in runner._prepare_history (passing
    # an extra positional `reserved_tokens` arg), so the contract is broader
    # than pydantic-ai's `HistoryProcessor` type alias. Kept local to avoid
    # depending on a private pydantic-ai symbol.
    HistoryProcessor = Callable[..., Awaitable[list[ModelMessage]]]


def _wrap_tool(tool: "Tool | ToolFuncEither") -> "Tool | ToolFuncEither":
    """Wrap a tool with error handling to prevent crashes."""
    if hasattr(tool, "function"):
        # lazy: heavy third-party
        from pydantic_ai import Tool as PydanticTool

        # It is a Tool instance
        original_func = getattr(tool, "function")
        safe_func = create_safe_wrapper(original_func, name=getattr(tool, "name"))
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
        # It is a callable (hasattr(tool, "function") is False, so not a Tool).
        return create_safe_wrapper(cast("Callable", tool))


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


def create_safe_wrapper(func: Callable, name: str | None = None) -> Callable:
    """Create a wrapper that catches exceptions and returns ToolReturn objects."""
    # lazy: heavy third-party
    from pydantic_ai import ToolReturn

    # lazy: circular — permission is a leaf module; capability is read at wrap
    # time (cheap) so the per-call gate need not re-import it.
    from zrb.llm.permission import tool_capability

    capability = tool_capability(func)
    tool_name = name or func.__name__

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            blocked = permission_gate(tool_name, capability, kwargs)
            if blocked is not None:
                return blocked
            blocked = sandbox_gate(tool_name, capability, kwargs)
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
                tool_args = await _fire_pre_tool_use(name, tool_args, ctx)
                if isinstance(tool_args, ToolReturn):
                    return tool_args  # PreToolUse hook denied the call
                blocked = permission_gate(name, tool_capability(tool), tool_args or {})
                if blocked is not None:
                    return blocked
                blocked = sandbox_gate(name, tool_capability(tool), tool_args or {})
                if blocked is not None:
                    return blocked
                result = await super().call_tool(name, tool_args, ctx, tool)
                # If result is already a ToolReturn, respect its framing; a
                # PostToolUse hook may still block it or replace its content.
                if isinstance(result, ToolReturn):
                    return await _fire_post_tool_use(name, tool_args, result)
                # Create a safe copy to prevent mutation by pydantic-ai
                safe_result = safe_copy_result(result)
                content, metadata = _truncated_content(to_string(safe_result))
                wrapped = ToolReturn(
                    return_value=safe_result,
                    content=content,
                    metadata=metadata,
                )
                return await _fire_post_tool_use(name, tool_args, wrapped)
            except Exception as e:
                await _fire_post_tool_use_failure(name, tool_args, e)
                error_msg = f"Error executing tool {name}: {e}"
                return ToolReturn(
                    return_value=None, content=error_msg, metadata={"error": True}
                )

    return SafeToolsetWrapper(toolset)


async def _fire_pre_tool_use(name: str, tool_args: dict[str, Any], ctx: Any) -> Any:
    """Fire PreToolUse for a tool about to execute (Claude-compatible).

    Skipped when ``ctx.tool_call_approved`` is True: that call came through the
    deferred-approval path, where PreToolUse already fired pre-approval (see
    ``deferred_calls.process_deferred_requests``). Returns the (possibly
    rewritten) ``tool_args`` to use, or a blocking ``ToolReturn`` if a hook denied
    the call.
    """
    # lazy: heavy third-party deferral
    from pydantic_ai import ToolReturn

    if getattr(ctx, "tool_call_approved", False):
        return tool_args
    results = await hook_manager.execute_hooks(
        HookEvent.PRE_TOOL_USE,
        {
            "tool": name,
            "args": tool_args,
            "call_id": getattr(ctx, "tool_call_id", None),
        },
        # Claude-standard context fields: a hook reads `tool_name`/`tool_input`
        # from stdin and tool-name matchers filter on `tool_name`. Without these
        # the matcher sees None and the hook silently never fires.
        tool_name=name,
        tool_input=tool_args,
    )
    decision = extract_pre_tool_decision(results)
    if decision.deny:
        return ToolReturn(
            return_value=None,
            content=(
                f"Blocked by PreToolUse hook: "
                f"{decision.reason or 'tool call denied'}"
            ),
            metadata={"blocked": True},
        )
    # Limitation: this is the execution-time path for tools that don't require
    # approval (no interactive prompt to show here), so a hook's
    # permissionDecision="ask" cannot force a prompt — it degrades to proceed.
    # "ask" is honored on the deferred-approval path (deferred_calls._resolve_approval).
    if decision.force_prompt:
        CFG.LOGGER.debug(
            f"PreToolUse hook requested 'ask' for {name} on the execution-time "
            "path (no prompt mechanism); proceeding."
        )
    if decision.updated_input and isinstance(tool_args, dict):
        return {**tool_args, **decision.updated_input}
    return tool_args


def _tool_response_payload(result: Any) -> dict[str, Any]:
    """Best-effort Claude-shaped ``tool_response``: a JSON-serializable dict.

    Claude's PostToolUse payload carries the tool's output under ``tool_response``.
    The result here may be a pydantic-ai ``ToolReturn`` (use its model-facing
    ``content``), a plain dict, or an arbitrary value. Wrap non-dicts under a
    ``content`` key and stringify anything that won't serialize so the stdin
    payload never falls back to the minimal event-only form.
    """
    content = getattr(result, "content", result)
    if isinstance(content, dict):
        payload = content
    else:
        payload = {"content": content}
    try:
        json.dumps(payload)
        return payload
    except (TypeError, ValueError):
        return {"content": str(content)}


async def _fire_post_tool_use(name: str, tool_args: dict[str, Any], result: Any) -> Any:
    """Fire PostToolUse after a successful tool call (Claude-compatible).

    A hook may block the result (discard it, feed the reason to the model) or
    replace the model-facing content via ``updatedToolOutput``. Returns the
    ``ToolReturn`` to surface.
    """
    # lazy: heavy third-party deferral
    from pydantic_ai import ToolReturn

    results = await hook_manager.execute_hooks(
        HookEvent.POST_TOOL_USE,
        {"tool": name, "args": tool_args, "result": result},
        # Claude-standard context fields (see _fire_pre_tool_use). PostToolUse
        # additionally carries `tool_response`; coerce to a JSON-safe dict so the
        # stdin payload and CLAUDE_TOOL_RESPONSE env var serialize cleanly.
        tool_name=name,
        tool_input=tool_args,
        tool_response=_tool_response_payload(result),
    )
    decision = extract_post_tool_decision(results)
    if decision.block:
        return ToolReturn(
            return_value=None,
            content=(
                f"Tool result blocked by PostToolUse hook: " f"{decision.reason or ''}"
            ),
            metadata={"blocked": True},
        )
    if decision.updated_output is not None and isinstance(result, ToolReturn):
        result = ToolReturn(
            return_value=result.return_value,
            content=decision.updated_output,
            metadata=result.metadata,
        )
    # Claude injects a PostToolUse hook's additionalContext into the model's
    # context after the tool result; render it by appending to the model-facing
    # content (the only post-tool injection point available here).
    if decision.additional_context:
        result = _append_tool_context(result, decision.additional_context)
    return result


def _append_tool_context(result: Any, extra: str) -> Any:
    """Append a PostToolUse hook's additionalContext to the model-facing output.

    Extends the ``ToolReturn`` content so the model sees the tool result followed
    by the hook's context. A non-``ToolReturn`` result is wrapped, preserving the
    original value for the model while surfacing the context.
    """
    # lazy: heavy third-party
    from pydantic_ai import ToolReturn

    if isinstance(result, ToolReturn):
        content = result.content
        return ToolReturn(
            return_value=result.return_value,
            content=_merge_content(content, extra),
            metadata=result.metadata,
        )
    return ToolReturn(return_value=result, content=_merge_content(result, extra))


def _merge_content(content: Any, extra: str) -> Any:
    """Append ``extra`` to existing tool content, preserving its shape.

    Strings are concatenated; sequence content (pydantic-ai allows a list of
    content parts) gets ``extra`` appended as a new part; anything else is paired
    with ``extra`` in a list so neither value is stringified away.
    """
    if content is None or content == "":
        return extra
    if isinstance(content, str):
        return f"{content}\n\n{extra}"
    if isinstance(content, (list, tuple)):
        return [*content, extra]
    return [content, extra]


async def _fire_post_tool_use_failure(
    name: str, tool_args: dict[str, Any], error: Exception
) -> None:
    """Fire PostToolUseFailure after a tool raised (observe-only, never raises)."""
    try:
        await hook_manager.execute_hooks(
            HookEvent.POST_TOOL_USE_FAILURE,
            {"tool": name, "args": tool_args, "error": str(error)},
            # Claude-standard context fields so tool-name matchers and stdin
            # reads work on the failure path too (see _fire_pre_tool_use).
            tool_name=name,
            tool_input=tool_args,
        )
    except Exception:
        # A misbehaving failure hook must not mask the original tool error.
        CFG.LOGGER.debug("PostToolUseFailure hook raised", exc_info=True)


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
    yolo: bool | Callable[[Any], bool] = False,
    resolve_model: bool = True,
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
        # Wrap the function toolset too, so SafeToolsetWrapper.call_tool is the
        # single chokepoint every tool call passes through (free functions and
        # toolset tools alike). This is where PreToolUse/PostToolUse fire.
        effective_toolsets.append(
            _wrap_toolset(
                FunctionToolset(tools=safe_tools, max_retries=CFG.LLM_TOOL_MAX_RETRIES)
            )
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

    # Resolve through model_getter/model_renderer here unless the caller already
    # did so (resolve_model=False). Resolving a second time would re-fire those
    # callbacks on an already-resolved value — which can feed a Model object into
    # a getter that expects a tier string. See LLMTask._create_agent.
    final_model = default_llm_config.resolve_model(model) if resolve_model else model
    effective_retries = retries if retries is not None else CFG.LLM_TOOL_MAX_RETRIES
    effective_model_settings = _apply_capability_constraints(
        model, final_model, model_settings
    )

    agent = Agent(
        model=final_model,
        # final_output_type may be `output_type | DeferredToolRequests`, a union
        # pydantic-ai accepts at runtime but its OutputSpec param type doesn't model.
        output_type=cast("OutputSpec[Any]", final_output_type),
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
    agent.zrb_history_processors = history_processors or []  # type: ignore[attr-defined]
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
