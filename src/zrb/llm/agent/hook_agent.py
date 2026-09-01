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
from zrb.llm.agent.subagent.manager import sub_agent_manager
from zrb.llm.agent.subagent.tool_resolver import resolve_tools_by_name
from zrb.llm.common_tools import ensure_common_tools
from zrb.llm.hook.agent_hook_registry import register_agent_hook_builder
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.schema import AgentHookConfig


def create_agent_hook(config: AgentHookConfig) -> HookCallable:
    async def agent_hook(context: HookContext) -> HookResult:
        """Run an agent with the configured system prompt over the event payload."""
        # lazy: zrb internal (heavy via transitive) — this edge isn't itself
        # circular, but hook.creator's own create_agent import used to be
        # (zrb.llm.agent's package __init__ imports this module at module
        # level). Deferring this import (and hook/manager.py's matching one)
        # keeps hook.creator out of zrb.llm.agent's eager import closure
        # entirely, verified by walking that closure — not just by checking
        # this one call site — so its own create_agent import no longer
        # needs the circular workaround.
        from zrb.llm.hook.creator import run_llm_hook

        resolved_tools = resolve_agent_hook_tools(config.tools)
        if config.tools and not resolved_tools:
            # Every named tool failed to resolve — most commonly because it's
            # config-gated and currently off (e.g. the journal tools while
            # LLM_JOURNAL_ENABLED is false). An agent whose whole job is
            # calling tools it doesn't have can only produce empty prose, so
            # skip the LLM call entirely rather than pay for one that cannot
            # do anything. A hook that genuinely wants zero tools leaves
            # `tools` empty from the start and is unaffected by this check.
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
            user_prompt=_agent_hook_input(context),
            tools=resolved_tools,
        )

    return agent_hook


def resolve_agent_hook_tools(names: list[str]) -> list:
    """Resolve `AgentHookConfig.tools` (names, Claude-compatible aliases
    honored) into real tool callables — including config-gated tools like the
    journal ones, which live behind factories rather than the static
    registry."""
    if not names:
        return []
    ensure_common_tools(sub_agent_manager)
    # Mirrors resolve_agent_build's own ctx-less fallback (subagent/manager.py)
    # — a hook fires outside any task run, so there is no real ctx to reuse.
    ctx = Context(
        shared_ctx=SharedContext(), task_name="agent-hook", color=0, icon="🪝"
    )
    resolved = resolve_tools_by_name(
        names,
        sub_agent_manager.get_tool_registry(),
        sub_agent_manager.get_tool_factories(),
        ctx,
    )
    # Same error containment every other agent gets (agent/common.py::create_agent):
    # a tool's `[SYSTEM SUGGESTION]` ValueError (e.g. journal_write's link check)
    # must come back as a tool result the model can act on, not an uncaught
    # exception that aborts the whole hook run.
    return [wrap_tool(_undeferred(tool)) for tool in resolved]


def _undeferred(tool: Any) -> Any:
    """Strip `defer_loading` from *tool* if the shared registry/factories set
    it (e.g. the journal tools, deferred for the main agent's rare use —
    see `common_tools.py::_seed_tool_factories`).

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


def _agent_hook_input(context: HookContext) -> str:
    """What to hand the agent as its user turn, best available first.

    A `history`/`turn` payload (a list of pydantic-ai `ModelMessage`) is
    rendered through the shared transcript renderer rather than `str()`'d —
    the raw payload is a dict of Python objects, not text a model should read.
    """
    payload = context.event_data
    if isinstance(payload, dict):
        messages = payload.get("turn") or payload.get("history")
        if messages:
            # lazy: heavy third-party (transitively imports pydantic_ai)
            from zrb.llm.util.history_formatter import format_history_as_text

            return format_history_as_text(messages, full=True)
    if payload:
        return str(payload)
    if context.prompt:
        return context.prompt
    return f"Hook event: {context.event.value}"


register_agent_hook_builder(create_agent_hook)
