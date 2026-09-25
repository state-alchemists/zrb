"""Background (fire-and-forget) subagent delegation.

``DelegateToAgentBackground`` starts a subagent and returns a handle
immediately; ``GetDelegationResult`` polls that handle. The synchronous
``DelegateToAgent`` path lives in ``delegate.py``.

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
from typing import TYPE_CHECKING, Annotated

from pydantic import Field

from zrb.config.config import CFG
from zrb.llm.agent.subagent.manager import (
    SubAgentManager,
)
from zrb.llm.agent.subagent.manager import (
    sub_agent_manager as default_sub_agent_manager,
)
from zrb.llm.agent_state import get_current_ui
from zrb.llm.permission import Capability, tag
from zrb.llm.tool.ambient_state import (
    get_current_tool_session,
    get_session_ownership_key,
)
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

    def _consume(self, handle: str) -> tuple[asyncio.Task | None, BufferedUI | None]:
        """Drop every record of *handle*; return its task and buffer."""
        self._agent_names.pop(handle, None)
        self._notified.discard(handle)
        return self._tasks.pop(handle, None), self._buffers.pop(handle, None)

    async def cancel(self, handle: str) -> str:
        """Cancel an outstanding background agent and consume its handle."""
        task, _ = self._consume(handle)
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

        _, buffered = self._consume(handle)
        # The buffer carries BufferedUI's terminal styling; this text becomes a
        # tool result for the parent model, which does not render escape codes.
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


# Handles this session's own DelegateToAgentBackground calls minted. A
# ContextVar rather than registry state: each chat session runs its own asyncio
# task, so this isolates sessions without a session-id key. The detached
# background task inherits a copy but never registers handles (sub-agents
# cannot delegate).
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
        agent_name: Annotated[
            str,
            Field(
                description=(
                    "Name of the sub-agent to delegate to (see AVAILABLE AGENTS "
                    "in this tool's description)."
                )
            ),
        ],
        deliverable: Annotated[
            str,
            Field(
                description=(
                    "Concrete artifact that must exist on return — name the "
                    "file, function, or decision."
                )
            ),
        ],
        task: Annotated[
            str,
            Field(
                description=(
                    "How to produce the deliverable — reference exact files, "
                    "line numbers, or commands when known."
                )
            ),
        ],
        non_goals: Annotated[
            list[str],
            Field(
                description=(
                    "Things the sub-agent must NOT do (scope clamp). Pass [] "
                    "only when certain there is no scope-expansion risk."
                )
            ),
        ],
        additional_context: Annotated[
            str,
            Field(
                description=(
                    "Extra background the sub-agent needs that doesn't belong "
                    "in deliverable/task/non_goals."
                )
            ),
        ] = "",
    ) -> str:
        """Start a subagent in the BACKGROUND and return a handle immediately.

        Poll with GetDelegationResult(handle) to collect the result later.

        The background agent inherits the main agent's permissions and yolo
        setting. If one of its tool calls needs approval, the request interrupts
        and prompts the user through the same UI (queued behind any current
        prompt), just like a synchronous delegate.
        """
        # Validate the name before detaching; inside the coroutine an unknown
        # agent would surface only when polled. get_agent_definition, not
        # create_agent: it is the same lookup create_agent uses, without
        # building the agent twice on the caller's turn.
        if not sub_agent_manager.get_agent_definition(agent_name):
            return agent_not_found_message(agent_name, sub_agent_manager)
        parent_ui = get_current_ui() or StdUI()
        handle = get_random_name(separator="-", add_random_digit=True)
        prefix = f"[{agent_name}:{handle}] "
        buffered_ui = BufferedUI(
            parent_ui,
            prefix=prefix,
            session_id=get_session_ownership_key(get_current_tool_session()),
        )

        # Context inheritance (yolo, permissions, approval) is described in
        # the module docstring.
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
    # Carry the agent roster in this tool's own description. cleandoc first:
    # an unindented roster appended under an 8-space docstring would pin that
    # indent on the whole description.
    delegate_to_agent_background.__doc__ = (
        f"{inspect.cleandoc(delegate_to_agent_background.__doc__ or '')}\n\n"
        f"AVAILABLE AGENTS:\n{agent_roster_doc(sub_agent_manager)}\n"
    )
    tag(delegate_to_agent_background, Capability.DELEGATE)
    return delegate_to_agent_background


def create_get_delegation_result_tool():
    async def get_delegation_result(
        handle: Annotated[
            str,
            Field(
                description=(
                    "The handle returned by DelegateToAgentBackground for the "
                    "background run to check."
                )
            ),
        ],
        wait: Annotated[
            float,
            Field(
                description=(
                    "Block up to this many seconds (capped by "
                    "LLM_BACKGROUND_WAIT_MAX), returning the instant the agent "
                    "finishes; on timeout, returns a 'still running' status "
                    "instead. 0 (default) returns immediately."
                )
            ),
        ] = 0,
        kill: Annotated[
            bool,
            Field(
                description=(
                    "True cancels the background agent instead of collecting "
                    "its result."
                )
            ),
        ] = False,
    ) -> str:
        """Return the result of a background delegation, or a 'still running'
        status. Once a completed result is collected, the handle is consumed.
        """
        if kill:
            return await _registry.cancel(handle)
        return await _registry.collect(handle, wait)

    get_delegation_result.__name__ = "GetDelegationResult"
    tag(get_delegation_result, Capability.META)
    return get_delegation_result
