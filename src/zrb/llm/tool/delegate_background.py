"""Background (fire-and-forget) subagent delegation.

Separate from the synchronous ``DelegateToAgent`` path (which is left untouched)
so there is zero regression risk to existing behavior. ``DelegateToAgentBackground``
starts a subagent and returns a handle immediately; ``GetDelegationResult`` polls
that handle.

Permissions and yolo are inherited: ``asyncio.ensure_future`` copies the current
``contextvars`` context when the task is created (while the parent run's
ContextVars are still set), so the background agent inherits the parent's UI,
yolo, permission policy, approval channel, and agent mode. When ``yolo=None``
(default, inherit), tool calls that need approval flow through the parent UI's
confirmation queue — the same path a synchronous delegate uses.

Caveat: the registry is process- and event-loop-scoped. Results are pollable for
the life of the running loop/session; they do not persist across process
restarts. A plan-mode parent cannot start a background agent — the tool is tagged
``DELEGATE`` and the execution gate denies it.
"""

from __future__ import annotations

import asyncio

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


def get_background_registry() -> _BackgroundRegistry:
    """Public accessor for the background-delegation registry."""
    return _registry


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
        speculative research, generating a file). For work whose result you need
        now, use the synchronous DelegateToAgent instead.

        The background agent inherits the main agent's permissions and yolo
        setting. If one of its tool calls needs approval, the request interrupts
        and prompts the user through the same UI (queued behind any current
        prompt), just like a synchronous delegate.

        REQUIRED ARGS mirror DelegateToAgent: agent_name, deliverable, task,
        non_goals (list; [] only when no scope-expansion risk). additional_context
        is optional.
        """
        parent_ui = get_current_ui() or StdUI()
        handle = get_random_name(separator="-", add_random_digit=True)
        prefix = f"[{agent_name}:{handle}] "
        buffered_ui = BufferedUI(parent_ui, prefix=prefix)

        # The detached task copies the current context (yolo, permission policy,
        # approval channel, UI), so the sub-agent inherits the main agent's
        # permissions and yolo setting (None → inherit). Its BufferedUI.ask_user
        # forwards approval prompts to the parent UI's confirmation queue, which
        # surfaces them to the user — the same path foreground delegate sub-agents
        # use.
        coro = _run_agent_task(
            agent_name=agent_name,
            deliverable=deliverable,
            non_goals=non_goals,
            task=task,
            additional_context=additional_context,
            sub_agent_manager=sub_agent_manager,
            ui=buffered_ui,
            yolo=None,  # None = inherit parent's yolo
        )

        _registry.start(handle, coro, buffered_ui)
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
