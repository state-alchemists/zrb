"""Resolution logic shared by `LLMTask` and `LLMChatTask`'s parts.

Both resolve tools, toolsets, system prompt, model, conversation name and the
permission-policy approval verdict from equivalent per-task attributes; one
implementation here keeps the two task types from drifting apart.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from zrb.llm.config.model_resolver import resolve_configured_model
from zrb.llm.factory_resolver import resolve_factory_items
from zrb.llm.permission import ALLOW, ASK, DENY, Capability, get_effective_policy
from zrb.util.attr import get_attr
from zrb.util.string.name import get_random_name

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext
    from zrb.llm.agent.types import AbstractToolset, Model, Tool, ToolFuncEither
    from zrb.llm.prompt.manager import PromptManager


def resolve_all_tools(
    ctx: AnyContext,
    tools: list[Tool | ToolFuncEither],
    tool_factories: list[
        Callable[[AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]]
    ],
) -> list[Tool | ToolFuncEither]:
    """Get all tools including those resolved from factories."""
    return resolve_factory_items(tools, tool_factories, ctx)


def resolve_all_toolsets(
    ctx: AnyContext,
    toolsets: list[AbstractToolset[None]],
    toolset_factories: list[Callable[[AnyContext], AbstractToolset[None]]],
) -> list[AbstractToolset[None]]:
    """Get all toolsets including those resolved from factories."""
    return resolve_factory_items(toolsets, toolset_factories, ctx)


def resolve_system_prompt(ctx: AnyContext, prompt_manager: PromptManager | None) -> str:
    """Compose the full system prompt for this run.

    Returns the empty string when the task has no prompt manager.
    """
    if prompt_manager is None:
        return ""
    compose_prompt = prompt_manager.compose_prompt()
    return compose_prompt(ctx)


def resolve_model(
    ctx: AnyContext,
    model: Any,
) -> str | Model:
    """The task's model, resolved against *ctx*, falling back to `CFG.LLM_MODEL`.

    A blank result counts as unset, so an empty ``--model`` input does not
    shadow the configured model.

    This is the single resolution point for a task's main model: an explicit
    name is resolved against `CFG.LLM_API_KEY`/`LLM_BASE_URL`/`LLM_PROVIDER`
    like the fallback, so a mid-session `/model <name>` (arriving as
    `ctx.input["model"]`) behaves like a configured one. Resolution is
    idempotent — an already-resolved `Model` passes through unchanged.
    """
    rendered_model = get_attr(ctx, model, None)
    if isinstance(rendered_model, str) and rendered_model.strip() == "":
        rendered_model = None
    return resolve_configured_model(rendered_model)


def apply_model_hooks(
    model: "str | Model",
    model_getter: "Callable[[str | Model | None], str | Model | None] | None",
    model_renderer: "Callable[[str | Model | None], str | Model | None] | None",
) -> "str | Model | None":
    """Apply *model_getter* then *model_renderer* to *model*.

    Either hook may return `None` (deferring to pydantic-ai's default), so the
    result is optional."""
    active = model_getter(model) if model_getter else model
    return model_renderer(active) if model_renderer else active


def resolve_conversation_name(
    ctx: AnyContext,
    conversation_name: Any,
) -> str:
    """The configured conversation name, or a fresh random one when blank."""
    resolved = str(get_attr(ctx, conversation_name, ""))
    if resolved.strip() == "":
        resolved = get_random_name()
    return resolved


def get_policy_skip_decision(
    tool_def: Any, cap_by_name: "dict[str, Capability] | None" = None
) -> bool | None:
    """Whether the effective permission policy skips approval for *tool_def*.

    ALLOW and DENY skip it (the gate blocks a DENY at execution); an explicit
    ASK is a hard ask. `None` means no policy or no matching rule, leaving the
    decision to yolo.
    """
    policy = get_effective_policy()
    if policy is None:
        return None
    tool_name = getattr(tool_def, "name", str(tool_def)) if tool_def is not None else ""
    cap = (cap_by_name or {}).get(tool_name, Capability.UNKNOWN)
    result = policy.decide(tool_name, cap, {})
    if result in (ALLOW, DENY):
        return True
    if result == ASK:
        return False
    return None
