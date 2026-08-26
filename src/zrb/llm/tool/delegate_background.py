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

``background_delegation_live_context`` (registered via
``PromptManager.add_live_context`` in ``builtin/llm/chat.py``) pushes a
one-line completion notice into the parent's next turn instead of leaving it
to remember to poll ``GetDelegationResult`` — session isolation for that
notice comes from ``_own_background_handles``, a ``ContextVar`` rather than a
field on the (process-global) registry, since each chat session already runs
its own asyncio task.
"""

from __future__ import annotations

import asyncio
import contextvars
import inspect
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.agent.run.runtime_state import get_current_ui
from zrb.llm.agent.subagent.manager import (
    SubAgentManager,
)
from zrb.llm.agent.subagent.manager import (
    sub_agent_manager as default_sub_agent_manager,
)
from zrb.llm.permission import Capability, tag
from zrb.llm.tool.ambient_state import get_current_tool_session
from zrb.llm.tool.delegate import (
    BufferedUI,
    agent_not_found_message,
    agent_roster_doc,
    run_agent_task,
)
from zrb.llm.ui.std_ui import StdUI
from zrb.util.cli.ansi import strip_ansi
from zrb.util.string.name import get_random_name

if TYPE_CHECKING:
    from zrb.context.any_context import AnyContext


class _BackgroundRegistry:
    """Process-lifetime registry of background delegation tasks keyed by handle."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}
        self._buffers: dict[str, BufferedUI] = {}
        self._agent_names: dict[str, str] = {}
        self._notified: set[str] = set()

    def start(
        self, handle: str, agent_name: str, coro, buffered_ui: BufferedUI
    ) -> None:
        self._tasks[handle] = asyncio.ensure_future(coro)
        self._buffers[handle] = buffered_ui
        self._agent_names[handle] = agent_name

    def peek_done(self, handles: set[str]) -> list[tuple[str, str]]:
        """Return (handle, agent_name) for handles that finished since the
        last call, without consuming them.

        Consumption for actual result retrieval still only happens through
        ``poll``/``collect`` — this only tracks whether a completion notice
        has already been surfaced once via the live-context hook.
        """
        newly_done = []
        for handle in handles:
            if handle in self._notified:
                continue
            task = self._tasks.get(handle)
            if task is not None and task.done():
                self._notified.add(handle)
                newly_done.append((handle, self._agent_names.get(handle, "?")))
        return newly_done

    async def collect(self, handle: str, wait: float = 0.0) -> str:
        """Poll a handle, optionally blocking up to ``wait`` seconds for it.

        Returns the instant the agent finishes; on timeout falls through to the
        synchronous ``poll`` (which reports "still running"). ``asyncio.wait``
        does not cancel the task on timeout, so the work keeps running.
        """
        task = self._tasks.get(handle)
        if task is not None and not task.done() and wait > 0:
            capped = min(wait, CFG.LLM_BACKGROUND_WAIT_MAX)
            await asyncio.wait({task}, timeout=capped)
        return self.poll(handle)

    async def cancel(self, handle: str) -> str:
        """Cancel an outstanding background agent and consume its handle."""
        task = self._tasks.pop(handle, None)
        self._buffers.pop(handle, None)
        self._agent_names.pop(handle, None)
        self._notified.discard(handle)
        if task is None:
            return (
                f"Unknown handle '{handle}'. [SYSTEM SUGGESTION]: it may have "
                "already been collected or killed, or never existed."
            )
        if not task.done():
            task.cancel()
        return f"Killed background agent '{handle}'."

    def poll(self, handle: str) -> str:
        task = self._tasks.get(handle)
        if task is None:
            return (
                f"Unknown handle '{handle}'. [SYSTEM SUGGESTION]: it may have "
                "already been collected, or never existed. Handles are returned "
                "by DelegateToAgentBackground."
            )
        if not task.done():
            return (
                f"Background agent '{handle}' is still running. Call "
                "GetDelegationResult again with wait=N to block up to N seconds, "
                "or kill=True to stop it."
            )

        # Consume the handle once collected.
        self._tasks.pop(handle, None)
        self._agent_names.pop(handle, None)
        self._notified.discard(handle)
        buffered = self._buffers.pop(handle, None)
        # strip_ansi: get_buffered_output() carries the muted styling BufferedUI
        # applies for its own live-viewer pane (agent_picker's Left/Right view) —
        # fine on a terminal, but this string is about to become tool-result text
        # in the parent model's context, which doesn't render escape codes.
        output = (
            strip_ansi(buffered.get_buffered_output()) if buffered is not None else ""
        )
        prefix = f"{output}\n" if output else ""

        try:
            result = task.result()
            body = result.result if result.success else f"Error: {result.error}"
            status = "completed"
        except Exception as e:  # noqa: BLE001
            body = f"failed: {e}"
            status = "failed"

        return f"[{handle}] {status}:\n\n{prefix}{body}"

    def cancel_all(self) -> None:
        """Cancel any outstanding background tasks (e.g. at session teardown)."""
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        self._tasks.clear()
        self._buffers.clear()
        self._agent_names.clear()
        self._notified.clear()


_registry = _BackgroundRegistry()


def get_background_registry() -> _BackgroundRegistry:
    """Public accessor for the background-delegation registry."""
    return _registry


# Handles this session's own DelegateToAgentBackground calls minted, scoped by
# ContextVar rather than kept on the (process-global) registry: each chat
# session runs its own asyncio task (`ChatSession.task_coroutine`), so the
# ContextVar naturally isolates one session's handles from another's, without
# a session-id dimension anywhere. `asyncio.ensure_future` in `_registry.start`
# copies this context into the detached background task too, but that task
# never calls `register_background_handle` itself (sub-agents can't delegate),
# so no cross-task mutation risk.
_own_background_handles: contextvars.ContextVar[set[str] | None] = (
    contextvars.ContextVar("own_background_handles", default=None)
)


def get_own_background_handles() -> set[str]:
    """Handles this session's own background delegations minted so far."""
    return _own_background_handles.get() or set()


def register_background_handle(handle: str) -> None:
    """Record *handle* as one this session started, for the live-context notice."""
    handles = _own_background_handles.get()
    if handles is None:
        handles = set()
        _own_background_handles.set(handles)
    handles.add(handle)


def background_delegation_live_context(ctx: "AnyContext") -> str | None:
    """Live-context provider: surface newly-finished background delegations.

    Registered via ``PromptManager.add_live_context`` so the parent agent
    learns a background delegation finished on its next turn, instead of
    having to remember to poll ``GetDelegationResult``. Matches the
    ``SimplePrompt`` signature (``Callable[[AnyContext], str | None]``), so
    *ctx* is required but unused here.
    """
    done = _registry.peek_done(get_own_background_handles())
    if not done:
        return None
    return "\n".join(
        f'Background delegation "{handle}" (agent: {agent_name}) has '
        f'completed — call GetDelegationResult(handle="{handle}") to '
        "retrieve it."
        for handle, agent_name in done
    )


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

        Poll with GetDelegationResult(handle) to collect the result later.

        The background agent inherits the main agent's permissions and yolo
        setting. If one of its tool calls needs approval, the request interrupts
        and prompts the user through the same UI (queued behind any current
        prompt), just like a synchronous delegate.

        REQUIRED ARGS mirror DelegateToAgent: agent_name, deliverable, task,
        non_goals (list; [] only when no scope-expansion risk). additional_context
        is optional.
        """
        # Resolve the name before detaching. run_agent_task would also catch an
        # unknown agent, but only inside the background coroutine — the model
        # would get "Started background agent 'reseacher'" and not learn the name
        # was wrong until it polled GetDelegationResult, if it ever did.
        #
        # get_agent_definition, not create_agent: create_agent runs every tool
        # factory, resolves the model, and composes the whole system prompt, and
        # run_agent_task calls it again inside the coroutine. Validating with it
        # would build the agent twice and put the first build on the caller's
        # turn — the wait this tool exists to avoid. It is also the same lookup
        # create_agent itself uses to decide the None return, so the check is
        # exactly as strict.
        if not sub_agent_manager.get_agent_definition(agent_name):
            return agent_not_found_message(agent_name, sub_agent_manager)
        parent_ui = get_current_ui() or StdUI()
        handle = get_random_name(separator="-", add_random_digit=True)
        prefix = f"[{agent_name}:{handle}] "
        buffered_ui = BufferedUI(
            parent_ui, prefix=prefix, session_id=get_current_tool_session()
        )

        # The detached task copies the current context (yolo, permission policy,
        # approval channel, UI), so the sub-agent inherits the main agent's
        # permissions and yolo setting (None → inherit). Its BufferedUI.ask_user
        # forwards approval prompts to the parent UI's confirmation queue, which
        # surfaces them to the user — the same path foreground delegate sub-agents
        # use.
        coro = run_agent_task(
            agent_name=agent_name,
            deliverable=deliverable,
            non_goals=non_goals,
            task=task,
            additional_context=additional_context,
            sub_agent_manager=sub_agent_manager,
            ui=buffered_ui,
            yolo=None,  # None = inherit parent's yolo
        )

        _registry.start(handle, agent_name, coro, buffered_ui)
        register_background_handle(handle)
        return (
            f"Started background agent '{agent_name}'. Handle: {handle}. "
            "Call GetDelegationResult with this handle to collect the result."
        )

    setattr(delegate_to_agent_background, "zrb_is_delegate_tool", True)
    delegate_to_agent_background.__name__ = "DelegateToAgentBackground"
    # Carry the roster in this tool's own schema. "mirrors DelegateToAgent" told
    # the model where the argument *shapes* come from, but the valid names were
    # never here — leaving it to recall them from a sibling tool's description.
    # cleandoc computes the common indent from the non-first lines, so an
    # unindented roster appended under an 8-space docstring pins that indent on
    # the whole description. Normalize before joining.
    delegate_to_agent_background.__doc__ = (
        f"{inspect.cleandoc(delegate_to_agent_background.__doc__ or '')}\n\n"
        f"AVAILABLE AGENTS:\n{agent_roster_doc(sub_agent_manager)}\n"
    )
    tag(delegate_to_agent_background, Capability.DELEGATE)
    return delegate_to_agent_background


def create_get_delegation_result_tool():
    async def get_delegation_result(
        handle: str,
        wait: float = 0,
        kill: bool = False,
    ) -> str:
        """Return the result of a background delegation, or a 'still running'
        status. Once a completed result is collected, the handle is consumed.

        Pass `wait=N` to block up to N seconds (capped by LLM_BACKGROUND_WAIT_MAX),
        returning the instant the agent finishes; on timeout it returns the
        'still running' status so you can call again with another `wait`, or stop
        the work with `kill=True`.
        """
        if kill:
            return await _registry.cancel(handle)
        return await _registry.collect(handle, wait)

    get_delegation_result.__name__ = "GetDelegationResult"
    tag(get_delegation_result, Capability.META)
    return get_delegation_result
