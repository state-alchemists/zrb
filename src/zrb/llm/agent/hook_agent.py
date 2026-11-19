"""Builds the `HookType.AGENT` hook callable — the one hook type implemented
as a real sub-agent turn, so it's the one hook builder that lives in the
agent package rather than in `hook/creator.py` (which builds command and
prompt hooks, neither of which needs the agent-building subsystem).

Registers itself into `hook.agent_hook_registry` as an import side effect
(see the bottom of this file and `agent/__init__.py`), so `hook/manager.py`
never has to import this module directly.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from zrb.context.context import Context
from zrb.context.shared_context import SharedContext
from zrb.llm.agent.common import wrap_tool

# Importing the seed is what gives `tool_registry` the built-in tools, which is
# the surface a hook resolves against — and the reason this module can answer
# "what is `Read`?" without a sub-agent manager.
from zrb.llm.agent.tool_seed import seed_default_tools  # noqa: F401
from zrb.llm.capabilities.hook.agent_hook_registry import register_agent_hook_builder
from zrb.llm.capabilities.hook.contracts.interface import HookCallable, HookContext, HookResult
from zrb.llm.capabilities.hook.contracts.schema import AgentHookConfig
from zrb.llm.contracts.shared.delegation_api import registered_sub_agent_manager
from zrb.llm.contracts.shared.tool_registry import tool_registry
from zrb.llm.contracts.shared.tool_resolver import resolve_tools_by_name, resolved_tool_name


def create_agent_hook(config: AgentHookConfig) -> HookCallable:
    async def agent_hook(context: HookContext) -> HookResult:
        """Run an agent with the configured system prompt over the event payload."""
        # lazy: zrb internal (heavy via transitive). Not itself circular, but
        # with hook/manager.py's matching deferral it keeps hook.creator out
        # of zrb.llm.agent's eager import closure.
        from zrb.llm.capabilities.hook.execution.creator import run_llm_hook

        resolved_tools = resolve_agent_hook_tools(config.tools)
        if config.tools and not resolved_tools:
            # Every named tool is unavailable (usually config-gated off), so
            # the LLM call could do nothing; skip it. A hook that wants zero
            # tools leaves `tools` empty and never reaches here.
            return HookResult(
                success=True,
                output=(
                    "Skipped: none of this hook's configured tools "
                    f"({', '.join(config.tools)}) are currently available."
                ),
            )
        return await run_llm_hook(
            kind="agent",
            model=config.model,
            system_prompt=config.system_prompt,
            user_prompt=_agent_hook_input(context, config),
            tools=resolved_tools,
            auto_approve=config.auto_approve,
        )

    return agent_hook


def resolve_agent_hook_tools(names: list[str]) -> list:
    """Resolve `AgentHookConfig.tools` (names, Claude-compatible aliases
    honored) into real tool callables — including config-gated tools like the
    memory ones, which live behind factories rather than the static registry.

    Two surfaces are merged: what zrb ships to every agent — `tool_registry`,
    which `agent/tool_seed.py` fills — and whatever a host registered on the
    delegation manager, which a hook has always been able to name and which
    wins a collision, as it does for a sub-agent. The manager is asked through
    `shared/delegation_api.py`: an agent may not import the subagent package,
    and a manager nobody loaded cannot be holding a registration.
    """
    if not names:
        return []
    # Mirrors resolve_agent_build's own ctx-less fallback (subagent/building.py)
    # — a hook fires outside any task run, so there is no real ctx to reuse.
    ctx = Context(
        shared_ctx=SharedContext(), task_name="agent-hook", color=0, icon="🪝"
    )
    tools, factories = _hook_tool_surface()
    resolved = resolve_tools_by_name(names, tools, factories, ctx)
    # Same error containment as create_agent: a `[SYSTEM SUGGESTION]` error
    # returns as a tool result instead of aborting the hook run.
    return [wrap_tool(_undeferred(tool)) for tool in _first_by_name(resolved)]


def _hook_tool_surface() -> "tuple[dict[str, Any], list[Any]]":
    """The tools and factories a hook resolves a name against."""
    manager = registered_sub_agent_manager()
    if manager is None:
        return tool_registry.tools_by_name(), list(tool_registry.get_tool_factories())
    return (
        dict(manager.get_tool_registry()),
        [*manager.get_tool_factories(), *tool_registry.get_tool_factories()],
    )


def _first_by_name(tools: list) -> list:
    """One tool per name, the earlier one kept.

    A host may register a factory that produces a tool the shipped set also
    produces; the manager's factories come first, so the host's copy is the one
    that reaches the hook, and the agent never receives two tools with one name.
    """
    seen: set[str] = set()
    kept: list = []
    for tool in tools:
        name = resolved_tool_name(tool)
        if name is not None:
            if name in seen:
                continue
            seen.add(name)
        kept.append(tool)
    return kept


def _undeferred(tool: Any) -> Any:
    """Strip `defer_loading` from *tool* if the shared registry/factories set
    it (e.g. a tool deferred for the main agent's rare use — see
    `agent/tool_seed.py::seed_tool_factories`).

    A hook names its tools explicitly in its own config; there is no big
    catalogue for `defer_loading` to hide a rare tool inside, so all it would
    do here is force an extra search-then-call round trip on every hook run
    that needs the tool, which is most of them.
    """
    if getattr(tool, "defer_loading", False):
        try:
            return dataclasses.replace(tool, defer_loading=False)
        except TypeError:
            return tool
    return tool


def _agent_hook_input(context: HookContext, config: AgentHookConfig) -> str:
    """What to hand the agent as its user turn: the event, then the config's note.

    A `history`/`turn` payload (a list of pydantic-ai `ModelMessage`) is
    rendered through the shared transcript renderer rather than `str()`'d —
    the raw payload is a dict of Python objects, not text a model should read.

    `input_note` follows it because a hook can need the state of a file and not
    only the event. A note that cannot be built leaves the turn as it was: the
    hook's own write is what reports the failure, and a reviewer that never ran
    would be a worse answer than one that ran without the extra paragraph.
    """
    text = _event_text(context)
    try:
        note = config.input_note(context).strip() if config.input_note else ""
    except OSError:
        return text
    return f"{text}\n\n{note}" if note else text


def _event_text(context: HookContext) -> str:
    """The event's own payload, as text an agent can read."""
    payload = context.event_data
    if isinstance(payload, dict):
        messages = payload.get("turn") or payload.get("history")
        if messages:
            # lazy: heavy third-party (transitively imports pydantic_ai)
            from zrb.llm.contracts.util.history_formatter import format_history_as_text

            return format_history_as_text(messages, full=True)
    if payload:
        return str(payload)
    if context.prompt:
        return context.prompt
    return f"Hook event: {context.event.value}"


register_agent_hook_builder(create_agent_hook)
