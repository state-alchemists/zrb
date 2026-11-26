"""Resolution logic shared by `LLMTask` and `LLMChatTask`'s parts."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from zrb.llm.capabilities.permission import (
    ALLOW,
    ASK,
    DENY,
    Capability,
    get_effective_policy,
    tool_capability,
)
from zrb.llm.contracts.config.model_resolver import resolve_configured_model
from zrb.llm.contracts.shared.factory_resolver import resolve_factory_items
from zrb.llm.engine.agent.run.error_classifier import retry_unless_permanent
from zrb.llm.engine.agent.run.hard_asks import get_llm_tool_name, is_hard_ask_call
from zrb.llm.engine.agent.run.tool_capabilities import register_tool_capabilities
from zrb.util.attr import get_attr, get_bool_attr
from zrb.util.string.name import get_random_name

if TYPE_CHECKING:
    from typing import TypeAlias

    from zrb.attr.type import BoolAttr, StrAttr
    from zrb.context.any_context import AnyContext
    from zrb.llm.capabilities.prompt.manager import PromptManager
    from zrb.llm.engine.agent.types import AbstractToolset, Model, Tool, ToolFuncEither
    from zrb.task.base.params import BaseTaskParams

    #: Builds tools for one run from the task context.
    ToolFactory: TypeAlias = Callable[
        [AnyContext], Tool | ToolFuncEither | list[Tool | ToolFuncEither]
    ]
    #: A model as a task stores it: rendered per context, or literal.
    ModelAttr: TypeAlias = (
        Callable[[AnyContext], Model | str | None] | Model | str | None
    )


def set_default_retry_if(kwargs: BaseTaskParams) -> None:
    """Make a task retry only errors the classifier does not call permanent."""
    if kwargs.get("retry_if") is None:
        kwargs["retry_if"] = retry_unless_permanent


def resolve_all_tools(
    ctx: AnyContext,
    tools: list[Tool | ToolFuncEither],
    tool_factories: list[ToolFactory],
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
    model: ModelAttr,
) -> str | Model:
    """The task's model, resolved against *ctx*, falling back to `CFG.LLM_MODEL`.

    A blank value counts as unset. An explicit name (e.g. from `/model`) is
    resolved against the configured provider credentials like the fallback; a
    `Model` passes through unchanged.
    """
    rendered_model = get_attr(ctx, model, None)
    if isinstance(rendered_model, str) and rendered_model.strip() == "":
        rendered_model = None
    return resolve_configured_model(rendered_model)


def resolve_conversation_name(
    ctx: AnyContext,
    conversation_name: StrAttr | None,
) -> str:
    """The configured conversation name, or a fresh random one when blank."""
    resolved = str(get_attr(ctx, conversation_name, ""))
    if resolved.strip() == "":
        resolved = get_random_name()
    return resolved


def build_capability_map(tools: "list[Tool | ToolFuncEither]") -> dict[str, Capability]:
    """LLM-visible name → capability for *tools*, keyed by the name the model calls.

    One map serves both halves of the gate on a call: the skip decision below,
    which needs it before the call is deferred, and the approval cascade, which
    needs it after — a deferred `ToolCallPart` carries no capability tag of its
    own (see `engine/agent/run/tool_capabilities.py`).
    """
    return {
        (getattr(tool, "name", None) or getattr(tool, "__name__", "")): tool_capability(
            tool
        )
        for tool in tools
    }


def get_policy_skip_decision(
    tool_def: object,
    cap_by_name: "dict[str, Capability] | None" = None,
    args: dict | None = None,
) -> bool | None:
    """Whether the effective permission policy skips approval for *tool_def*.

    ALLOW and DENY skip it (the gate blocks a DENY at execution); an explicit
    ASK is a hard ask. `None` means no policy or no matching rule, leaving the
    decision to yolo.

    *args* is the call's arguments; without them an `arg_pattern` rule cannot
    match and yolo would decide in its place.
    """
    policy = get_effective_policy()
    if policy is None:
        return None
    tool_name = getattr(tool_def, "name", str(tool_def)) if tool_def is not None else ""
    cap = (cap_by_name or {}).get(tool_name, Capability.UNKNOWN)
    result = policy.decide(tool_name, cap, args or {})
    if result in (ALLOW, DENY):
        return True
    if result == ASK:
        return False
    return None


def make_skip_approval_decision(
    cap_by_name: "dict[str, Capability]",
    fallback: Callable[..., bool],
) -> Callable[..., bool]:
    """Build the predicate deciding whether a tool call skips approval.

    A hard ask is never skipped, whoever would have allowed it: leaving the
    sandbox and writing the MCP config are a human's decision, and a policy
    `allow` answers about ordinary calls (ADR-0065, ADR-0146). Then the
    permission policy decides (see `get_policy_skip_decision`), and *fallback*
    last — a live xcom for `LLMChatTask`, a snapshot for a bare `LLMTask`. Tool
    policies run later, in `deferred_calls.py`.
    """

    def should_skip_approval(tool_def=None, args=None):
        if is_hard_ask_call(get_llm_tool_name(tool_def), args):
            return False
        decision = get_policy_skip_decision(tool_def, cap_by_name, args)
        if decision is not None:
            return decision
        return fallback(tool_def, args)

    return should_skip_approval


def resolve_skip_approval(
    ctx: AnyContext, yolo: BoolAttr, tools: "list[Tool | ToolFuncEither]"
) -> Callable[..., bool]:
    """The skip decision for a task whose yolo is a plain attribute.

    Registers the capability map the decision reads first: a bare `LLMTask` used
    to register none, so `edit:ask` read every tool as UNKNOWN and the later
    `*:allow` answered instead. Yolo is snapshotted — it is a `BoolAttr` here,
    not `LLMChatTask`'s live xcom.
    """
    cap_by_name = build_capability_map(tools)
    register_tool_capabilities(cap_by_name)
    yolo_on = get_bool_attr(ctx, yolo, False)
    return make_skip_approval_decision(cap_by_name, lambda *_: yolo_on)
