from __future__ import annotations

import asyncio
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
from zrb.llm.agent.tool_result import has_multimodal, tool_return
from zrb.llm.agent.truncate import truncate_tool_content
from zrb.llm.config.config import llm_config as default_llm_config
from zrb.llm.hook.manager import hook_manager
from zrb.llm.hook.types import HookEvent
from zrb.llm.util.capabilities import model_capabilities
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


def wrap_tool(tool: "Tool | ToolFuncEither") -> "Tool | ToolFuncEither":
    """Wrap a tool with error handling to prevent crashes."""
    # lazy: tests patch zrb.llm.permission.tool_capability; hoisting would
    # bind the name at this module's load time and bypass the mock.
    from zrb.llm.permission import capability_metadata, tool_capability

    if hasattr(tool, "function"):
        # lazy: heavy third-party
        from pydantic_ai import Tool as PydanticTool

        # It is a Tool instance (or a duck-typed equivalent)
        original_func = getattr(tool, "function")
        safe_func = create_safe_wrapper(original_func, name=getattr(tool, "name", None))
        metadata = {
            **(getattr(tool, "metadata", None) or {}),
            **capability_metadata(tool_capability(tool)),
        }
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
                defer_loading=tool.defer_loading,
                metadata=metadata,
            )
        # Duck-typed tool: rebuild as a real Tool around the safe wrapper.
        # Returning the original unchanged would silently drop both the error
        # containment of safe_func and the capability tag — an untagged tool
        # resolves to UNKNOWN and is denied by conservative policies.
        return PydanticTool(
            safe_func,
            name=getattr(tool, "name", None),
            description=getattr(tool, "description", None),
            takes_ctx=bool(getattr(tool, "takes_ctx", False)),
            metadata=metadata,
        )
    else:
        # It is a callable (hasattr(tool, "function") is False, so not a Tool).
        # Wrapped into a Tool (rather than left bare) so the capability tag
        # survives as ToolDefinition.metadata: the outer SafeToolsetWrapper
        # gate (see _wrap_toolset below) only ever sees a ToolsetTool, which
        # carries a tool_def but no .function and no arbitrary attributes, so
        # a tag() set on the raw callable would otherwise resolve as UNKNOWN
        # there and be denied outright by policies like PLAN_MODE_POLICY.
        # lazy: heavy third-party
        from pydantic_ai import Tool as PydanticTool

        safe_func = create_safe_wrapper(cast("Callable", tool))
        return PydanticTool(
            safe_func, metadata=capability_metadata(tool_capability(tool))
        )


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
    # Other types (tuples especially) may still hold mutable elements.
    try:
        return copy.deepcopy(result)
    except Exception:
        # Un-copyable objects (open handles, locks) pass through as-is.
        return result


def _oversize_metadata(value: Any) -> dict[str, Any]:
    """Flag an oversized tool result in metadata, without rewriting it.

    ``CFG.LLM_MAX_TOOL_RESULT_CHARS`` does not bound what the model reads (see
    ADR-0043): the field that becomes the tool-result message goes through
    whole. The size is recorded and the value is passed through untouched.

    Metadata never reaches the model; it is there so a real cap can be decided
    on evidence.

    Multimodal content is not measured at all — its text rendering is a repr,
    not the file, so a character count of it would be meaningless.
    """
    if has_multimodal(value):
        return {}
    rendered = value if isinstance(value, str) else to_string(value)
    _, is_oversized = truncate_tool_content(
        rendered, limit=CFG.LLM_MAX_TOOL_RESULT_CHARS
    )
    if not is_oversized:
        return {}
    return {"oversized": True, "original_chars": len(rendered)}


def create_safe_wrapper(func: Callable, name: str | None = None) -> Callable:
    """Create a wrapper that catches exceptions and returns ToolReturn objects."""
    # lazy: heavy third-party
    from pydantic_ai import ModelRetry, ToolReturn

    # lazy: tests patch zrb.llm.permission.tool_capability; hoisting would
    # bind the name at this module's load time and bypass the mock.
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
                # This wrapper is a coroutine function, so pydantic-ai never
                # applies its own executor offload for sync tools — inline they
                # would block the TUI's event loop for the tool's duration
                # (ReadFile on a big file, grep, journal search). ContextVars
                # propagate into the thread; none of the sync tools write them.
                result = await asyncio.to_thread(func, *args, **kwargs)

            # If result is already a ToolReturn, return it as-is. The tool framed
            # its own content (possibly truncated deliberately) — respect it.
            if isinstance(result, ToolReturn):
                return result

            # Create a safe copy to prevent mutation by pydantic-ai
            safe_result = safe_copy_result(result)

            # Otherwise wrap the successful result untouched — see
            # _oversize_metadata for why the size cap does not rewrite it.
            return tool_return(safe_result, **_oversize_metadata(safe_result))
        except ModelRetry:
            # pydantic-ai's retry protocol: the framework turns this into a
            # retry prompt for the model. Swallowing it into an error string
            # would disable retries for every tool.
            raise
        except Exception as e:
            error_msg = f"Error executing tool {func.__name__}: {e}"
            return tool_return(error_msg, error=True)

    return wrapper


def _wrap_toolset(toolset: "AbstractToolset[None]") -> "AbstractToolset[None]":
    """Wrap a toolset with error handling."""
    # lazy: heavy third-party
    from pydantic_ai import ModelRetry, ToolReturn
    from pydantic_ai.toolsets import WrapperToolset

    # lazy: tests patch zrb.llm.permission.tool_capability; hoisting would
    # bind the name at this module's load time and bypass the mock.
    from zrb.llm.permission import tool_capability
    from zrb.llm.tool_call.override_registry import pop_override_note

    class SafeToolsetWrapper(WrapperToolset[None]):
        async def call_tool(
            self, name: str, tool_args: dict[str, Any], ctx: Any, tool: Any
        ) -> Any:
            # Consumed once per call, regardless of outcome: if the user edited
            # this call's arguments during approval, the model's own turn in
            # history still shows what it originally wrote (pydantic-ai never
            # rewrites that ToolCallPart) — this note is the only place left to
            # tell it what actually ran. See override_registry's docstring.
            override_note = pop_override_note(getattr(ctx, "tool_call_id", None))

            def _with_override_note(result: Any) -> Any:
                return (
                    _append_tool_context(result, override_note)
                    if override_note
                    else result
                )

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
                    result = await _fire_post_tool_use(name, tool_args, result)
                    return _with_override_note(result)
                # Create a safe copy to prevent mutation by pydantic-ai
                safe_result = safe_copy_result(result)
                wrapped = tool_return(safe_result, **_oversize_metadata(safe_result))
                wrapped = await _fire_post_tool_use(name, tool_args, wrapped)
                return _with_override_note(wrapped)
            except ModelRetry:
                # Part of pydantic-ai's retry protocol — must reach the
                # framework, not become an opaque error string.
                raise
            except Exception as e:
                await _fire_post_tool_use_failure(name, tool_args, e)
                error_msg = f"Error executing tool {name}: {e}"
                return _with_override_note(tool_return(error_msg, error=True))

    return SafeToolsetWrapper(toolset)


async def _fire_pre_tool_use(name: str, tool_args: dict[str, Any], ctx: Any) -> Any:
    """Fire PreToolUse for a tool about to execute (Claude-compatible).

    Skipped when ``ctx.tool_call_approved`` is True: that call came through the
    deferred-approval path, where PreToolUse already fired pre-approval (see
    ``deferred_calls.process_deferred_requests``). Returns the (possibly
    rewritten) ``tool_args`` to use, or a blocking ``ToolReturn`` if a hook denied
    the call.
    """
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
        return tool_return(
            f"Blocked by PreToolUse hook: {decision.reason or 'tool call denied'}",
            blocked=True,
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
    ``return_value``), a plain dict, or an arbitrary value. Wrap non-dicts under a
    ``content`` key and stringify anything that won't serialize so the stdin
    payload never falls back to the minimal event-only form.
    """
    content = getattr(result, "return_value", result)
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
        return tool_return(
            f"Tool result blocked by PostToolUse hook: {decision.reason or ''}",
            blocked=True,
        )
    if decision.updated_output is not None and isinstance(result, ToolReturn):
        result = ToolReturn(
            return_value=decision.updated_output,
            content=result.content,
            metadata=result.metadata,
        )
    # Claude injects a PostToolUse hook's additionalContext into the model's
    # context after the tool result; render it by appending to the model-facing
    # output (the only post-tool injection point available here).
    if decision.additional_context:
        result = _append_tool_context(result, decision.additional_context)
    return result


def _append_tool_context(result: Any, extra: str) -> Any:
    """Append a PostToolUse hook's additionalContext to the model-facing output.

    Extends the ``ToolReturn`` return value so the model sees the tool result
    followed by the hook's context in the same tool-result message. A
    non-``ToolReturn`` result is wrapped the same way.
    """
    # lazy: heavy third-party
    from pydantic_ai import ToolReturn

    if isinstance(result, ToolReturn):
        return ToolReturn(
            return_value=_merge_content(result.return_value, extra),
            content=result.content,
            metadata=result.metadata,
        )
    return tool_return(_merge_content(result, extra))


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

    effective_system_prompt = expand_prompt(system_prompt)

    safe_tools = [wrap_tool(t) for t in tools]
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
    effective_model_settings = _apply_request_timeout(
        _apply_reasoning_defaults(
            _apply_capability_constraints(model, final_model, model_settings),
            model if isinstance(model, str) else final_model,
        )
    )

    agent: "Agent[None, Any]" = Agent(
        model=final_model,
        # Pins AgentDepsT=None so the contravariant `toolsets`/`model_settings`
        # params below (all typed AbstractToolset[None]/etc.) resolve against
        # the right overload instead of the deps_type=object default.
        deps_type=type(None),
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
    # Ad-hoc attribute on the pydantic-ai agent; setattr keeps it honest
    # instead of a blanket type suppression.
    setattr(agent, "zrb_history_processors", history_processors or [])
    return agent


def _apply_request_timeout(
    model_settings: "ModelSettings | None",
) -> "ModelSettings | None":
    """Give every model request a deadline, from ``CFG.LLM_REQUEST_TIMEOUT``.

    Without one, a provider that accepts the connection and then stops sending
    blocks the run forever: pydantic-ai waits on the stream, and ``retry_loop``
    only fires on a raised exception, so a stall is indistinguishable from
    thinking. Observed as two benchmark cells that burned their full 600s
    wall-clock having produced no output, no history, and no file writes.

    ``LLM_REQUEST_TIMEOUT`` already existed and already documented itself as the
    "default timeout for LLM requests" — it was simply never read outside the
    web session runner. Applied here rather than at a call site so it covers the
    main agent, programmatic ``LLMTask``, and sub-agents alike. A caller that
    sets ``timeout`` itself wins; a non-positive value disables the deadline.
    """
    timeout_ms = CFG.LLM_REQUEST_TIMEOUT
    if timeout_ms <= 0:
        return model_settings
    if model_settings is None:
        return {"timeout": timeout_ms / 1000}
    if "timeout" in model_settings:
        return model_settings
    return {**model_settings, "timeout": timeout_ms / 1000}


def _apply_reasoning_defaults(
    model_settings: "ModelSettings | None",
    model: "Model | str | None",
) -> "ModelSettings | None":
    """Default to a visible, cached reasoning experience out of the box.

    Without ``openai_reasoning_summary``, OpenAI's Responses API returns a
    ``ThinkingPart`` with empty ``content`` and only an opaque encrypted
    ``signature`` — real reasoning happened, but nothing human-readable comes
    back (confirmed against a live session's persisted history: 1612 bytes of
    signature, zero characters of text). ``"auto"`` asks OpenAI to include a
    readable summary. ``openai_prompt_cache_retention="24h"`` extends how long
    OpenAI keeps a conversation's cached prefix warm (default is much
    shorter), which matters for zrb's usage pattern of resending a growing
    history on every turn; per pydantic-ai's own docs the two prompt-cache
    settings are independent of the newer GPT-5.6 ``openai_prompt_cache_options``
    mechanism, so setting both is safe.

    ``LLM_THINKING`` (unset by default) maps onto pydantic-ai's own
    cross-provider ``ModelSettings.thinking`` field, so one CFG knob controls
    reasoning effort across OpenAI/Anthropic/Google/etc. instead of a
    per-provider setting. Unlike OpenAI, Anthropic's thinking blocks already
    come back as readable text once ``thinking`` is enabled — no
    summary-equivalent default needed there.

    Google is the odd one out: Gemini 2.5/3 think (and bill
    ``thoughts_tokens``) whether or not a request sets ``thinking``, but only
    return the readable summary when ``thinking_config.include_thoughts`` is
    explicitly requested — confirmed against a live session: ``thoughts_tokens``
    non-zero on every turn, no thinking block ever rendered. Unlike OpenAI's
    fix, this can't be a blanket default: the same unified ``thinking`` field
    also drives Anthropic's *opt-in* extended thinking, so defaulting
    ``thinking=True`` for every model would turn that on too — a real
    cost/latency change, not a visibility fix. So the ``thinking=True``
    fallback below only fires when ``LLM_THINKING`` is unset *and* the
    resolved model is capability-flagged ``supports_thinking_summary``
    (currently Gemini 2.5/3 only, see ``zrb.llm.util.capabilities``) — Gemini
    already reasons by default, so this only makes the existing reasoning
    visible, it doesn't turn anything on that wasn't already running and
    billed.

    ``anthropic_cache="5m"`` requests Anthropic's automatic prompt-cache
    breakpoint (a top-level ``cache_control`` that the server moves forward
    as the conversation grows). Unlike OpenAI, Anthropic never caches a
    prompt unless a request asks for it — without this, zrb's
    resend-the-whole-history-every-turn pattern reprocesses the full
    conversation from scratch on every Anthropic call. "5m" is Anthropic's
    own default TTL; "1h" costs more per cache write and only pays off for
    gaps longer than 5 minutes between turns. Google has no request-level
    caching default to mirror this: Gemini's context caching is a
    pre-created cache *resource* (``google_cached_content``) that must be
    created and kept alive out-of-band via a separate API call — out of
    scope for a settings default.

    Every key here is either provider-namespaced (silently ignored by every
    other provider's model class — pydantic-ai's own convention, not
    something to special-case per model) or the provider-agnostic ``thinking``
    field. Caller-supplied ``model_settings`` always win, key by key.
    """
    # Untyped as a plain dict, not ModelSettings: the provider-namespaced keys
    # only exist on their own provider's ModelSettings subclass (e.g.
    # OpenAIChatModelSettings, AnthropicModelSettings), each more specific
    # than the provider-agnostic one this function (and every caller in the
    # chain) is typed against.
    defaults: dict[str, Any] = {
        "openai_reasoning_summary": "auto",
        "openai_prompt_cache_retention": "24h",
        "anthropic_cache": "5m",
    }
    if CFG.LLM_THINKING is not None:
        defaults["thinking"] = CFG.LLM_THINKING
    elif model_capabilities.get(model).supports_thinking_summary:
        defaults["thinking"] = True
    if model_settings is None:
        return cast("ModelSettings", defaults)
    return cast("ModelSettings", {**defaults, **model_settings})


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
       **prompt-side** parallel-tool-call line in the System Context
       section (see ``_format_parallel_tool_call_line`` in
       ``zrb.llm.prompt.system_context``) is what actually changes those
       models' behavior. Both layers use
       the same capability registry, so toggling
       ``supports_parallel_tool_calls`` in one place updates both.

    .. warning::

       Some providers reject ``parallel_tool_calls`` outright rather than
       honouring or ignoring it — OpenAI's o-series answers "Unsupported
       parameter: 'parallel_tool_calls' is not supported with this model" with
       a 400, and kimi-k2.5 behind NVIDIA NIM answers "This model only supports
       single tool-calls at once!". For such a model, declaring
       ``supports_parallel_tool_calls=False`` would send the one parameter that
       breaks every request — a worse failure than the batching it prevents.
       Splitting "malforms parallel calls" from "rejects the flag" into two
       fields is the fix if that case ever needs supporting; until then the
       registry comment on ``_NO_PARALLEL_TOOL_CALLS`` says to keep such models
       off the list.
    """
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
