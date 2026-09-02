"""Getter logic shared by `LLMTaskBuilding` (building.py) and `ChatExecution`
(chat/execution.py) — both resolve the same kind of value (tools, toolsets,
system prompt, model, conversation name) from equivalent per-task attributes.
One implementation here means the two decompositions cannot drift against
each other, the way their inline copies previously did.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from zrb.llm.config.model_resolver import resolve_configured_model
from zrb.llm.factory_resolver import resolve_factory_items
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
    render_model: bool,
) -> str | Model:
    """The task's model, rendered against *ctx*, falling back to `CFG.LLM_MODEL`.

    A blank render counts as unset, so an empty ``--model`` input does not
    shadow the configured model with an empty string. The task's own explicit
    `model` is returned as-is (matching the pre-Phase-6 behavior — only the
    `CFG` fallback goes through provider resolution); resolve it yourself via
    `zrb.llm.config.model_resolver.model_resolver` if you need that too.
    """
    rendered_model = get_attr(ctx, model, None, auto_render=render_model)
    if isinstance(rendered_model, str) and rendered_model.strip() == "":
        rendered_model = None
    if rendered_model is not None:
        return rendered_model
    return resolve_configured_model()


def apply_model_hooks(
    model: "str | Model",
    model_getter: "Callable[[str | Model | None], str | Model | None] | None",
    model_renderer: "Callable[[str | Model | None], str | Model | None] | None",
) -> "str | Model | None":
    """Apply *model_getter* then *model_renderer* to *model* — the task-level
    hooks a `zrb_init.py` sets (e.g. `task.model_getter = ...`) for per-task
    model tiering or A/B testing. Either may return `None` (e.g. to defer to
    pydantic-ai's own default), so the result is optional."""
    active = model_getter(model) if model_getter else model
    return model_renderer(active) if model_renderer else active


def resolve_conversation_name(
    ctx: AnyContext,
    conversation_name: Any,
    render_conversation_name: bool,
) -> str:
    """The configured conversation name, or a fresh random one when blank."""
    resolved = str(get_attr(ctx, conversation_name, "", render_conversation_name))
    if resolved.strip() == "":
        resolved = get_random_name()
    return resolved
