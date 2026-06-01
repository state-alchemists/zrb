"""Background (fire-and-forget) subagent delegation.

Separate from the synchronous ``DelegateToAgent`` path (which is left untouched)
so there is zero regression risk to existing behavior. ``DelegateToAgentBackground``
starts a subagent and returns a handle immediately; ``GetDelegationResult`` polls
that handle.

Ambient state is captured automatically: ``asyncio.ensure_future`` copies the
current ``contextvars`` context when the task is created (while the parent run's
ContextVars are still set), so the background agent inherits the parent's UI,
yolo, permission policy, and agent mode without a use-after-reset hazard.

Caveat: the registry is process- and event-loop-scoped. Results are pollable for
the life of the running loop/session; they do not persist across process
restarts. A plan-mode parent cannot start a background agent — the tool is tagged
``DELEGATE`` and the execution gate denies it.
"""

from __future__ import annotations

import asyncio
from typing import Any

from zrb.llm.agent.run.runtime_state import get_current_ui
from zrb.llm.agent.subagent.manager.manager import SubAgentManager
from zrb.llm.agent.subagent.manager.manager import (
    sub_agent_manager as default_sub_agent_manager,
)
from zrb.llm.permission import Capability, tag
from zrb.llm.tool.delegate import BufferedUI, _run_agent_task
from zrb.llm.ui.std_ui import StdUI
from zrb.util.string.name import get_random_name


class _BackgroundRegistry:
    """Process-lifetime registry of background delegation tasks keyed by handle."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}
        self._buffers: dict[str, BufferedUI] = {}

    def start(self, handle: str, coro, buffered_ui: BufferedUI) -> None:
        self._tasks[handle] = asyncio.ensure_future(coro)
        self._buffers[handle] = buffered_ui

    def poll(self, handle: str) -> str:
        task = self._tasks.get(handle)
        if task is None:
            return (
                f"Unknown handle '{handle}'. [SYSTEM SUGGESTION]: it may have "
                "already been collected, or never existed. Handles are returned "
                "by DelegateToAgentBackground."
            )
        if not task.done():
            return f"Background agent '{handle}' is still running. Poll again later."
        # Consume the handle once collected.
        self._tasks.pop(handle, None)
        buffered = self._buffers.pop(handle, None)
        output = buffered.get_buffered_output() if buffered is not None else ""
        try:
            result = task.result()
        except Exception as e:  # noqa: BLE001
            return f"[{handle}] failed: {e}"
        body = result.result if result.success else f"Error: {result.error}"
        prefix = f"{output}\n" if output else ""
        return f"[{handle}] completed:\n\n{prefix}{body}"

    def cancel_all(self) -> None:
        """Cancel any outstanding background tasks (e.g. at session teardown)."""
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        self._tasks.clear()
        self._buffers.clear()


_registry = _BackgroundRegistry()

# Shown to the model when a background agent attempts an action that would
# otherwise require interactive confirmation.
_BACKGROUND_DENY_MSG = (
    "Blocked: background agents run non-interactively and cannot prompt for "
    "confirmation, so this action was denied. Inherited auto-approval (yolo) "
    "and the active permission policy still apply — anything pre-approved runs. "
    "[SYSTEM SUGGESTION]: if this action genuinely needs approval, run it in the "
    "foreground with DelegateToAgent (or yourself) instead of in the background."
)


def get_background_registry() -> _BackgroundRegistry:
    """Public accessor for the background-delegation registry."""
    return _registry


def _install_background_guardrails() -> None:
    """Make the *current* (copied) context fail-closed and non-interactive.

    A background agent is detached from the turn that started it, so there is no
    safe way for it to drive the shared UI / approval channel for confirmation —
    doing so would race or hang the foreground agent. We therefore, inside the
    background task's own copied context (so the parent is unaffected):

    * replace the tool-confirmation handler with an auto-deny callable,
    * drop the approval channel so no remote/terminal prompt is attempted,
    * mark the run non-interactive so AskUserQuestion short-circuits.

    Tools the inherited yolo flag or permission policy already auto-approve still
    run normally (they never reach confirmation); everything else is denied with
    ``_BACKGROUND_DENY_MSG`` rather than blocking on a human.
    """
    # lazy: heavy third-party
    from pydantic_ai import ToolDenied

    from zrb.llm.agent.run.runner import current_tool_confirmation
    from zrb.llm.approval.approval_channel import current_approval_channel
    from zrb.llm.tool.ambient_state import set_interactive_mode

    def _auto_deny(_call: object) -> "ToolDenied":
        return ToolDenied(_BACKGROUND_DENY_MSG)

    current_tool_confirmation.set(_auto_deny)
    current_approval_channel.set(None)
    set_interactive_mode(False)


def create_background_delegate_tool(
    sub_agent_manager: SubAgentManager | None = None,
):
    if sub_agent_manager is None:
        sub_agent_manager = default_sub_agent_manager

    async def delegate_to_agent_background(
        agent_name: str,
        deliverable: str,
        task: str,
        non_goals: list[str],
        additional_context: str = "",
    ) -> str:
        """Start a subagent in the BACKGROUND and return a handle immediately.

        Poll with GetDelegationResult(handle) to collect the result later. Use
        for long, independent work you do not need before continuing (e.g.
        speculative research). For work whose result you need now, use the
        synchronous DelegateToAgent instead.

        REQUIRED ARGS mirror DelegateToAgent: agent_name, deliverable, task,
        non_goals (list; [] only when no scope-expansion risk). additional_context
        is optional.
        """
        parent_ui = get_current_ui() or StdUI()
        handle = get_random_name(separator="-", add_random_digit=True)
        prefix = f"[{agent_name}:{handle}] "
        buffered_ui = BufferedUI(parent_ui, prefix=prefix)

        async def _guarded() -> Any:
            # Runs in the task's own copied context (captured at task-creation
            # time, so yolo/policy/mode are inherited). Make it fail-closed and
            # non-interactive before the agent executes.
            _install_background_guardrails()
            return await _run_agent_task(
                agent_name=agent_name,
                deliverable=deliverable,
                non_goals=non_goals,
                task=task,
                additional_context=additional_context,
                sub_agent_manager=sub_agent_manager,
                ui=buffered_ui,
            )

        _registry.start(handle, _guarded(), buffered_ui)
        return (
            f"Started background agent '{agent_name}'. Handle: {handle}. "
            "Call GetDelegationResult with this handle to collect the result."
        )

    delegate_to_agent_background.zrb_is_delegate_tool = True
    delegate_to_agent_background.__name__ = "DelegateToAgentBackground"
    tag(delegate_to_agent_background, Capability.DELEGATE)
    return delegate_to_agent_background


def create_get_delegation_result_tool():
    async def get_delegation_result(handle: str) -> str:
        """Return the result of a background delegation, or a 'still running'
        status. Once a completed result is collected, the handle is consumed."""
        return _registry.poll(handle)

    get_delegation_result.__name__ = "GetDelegationResult"
    tag(get_delegation_result, Capability.META)
    return get_delegation_result
