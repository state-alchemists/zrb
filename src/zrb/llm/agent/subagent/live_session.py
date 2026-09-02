"""In-memory registry of live delegated sub-agent sessions — the "talk to a
running sub-agent directly" feature.

Distinct from `agent_activity_registry` (`zrb.llm.agent.activity`): that one
is a plain, JSON-serializable snapshot the web polling API reads (`snapshot()`)
and must stay that way. This registry holds live object references — a
`BufferedUI`, the sub-agent's own accumulated pydantic-ai message history —
scoped to the current process/session only, so a human can navigate into a
currently running (or just-finished) sub-agent's own view and keep talking to
it. Also distinct from the disk-persisted `/load` resume path,
which survives a process restart; this one does not and isn't meant to.

Two ways a message reaches the sub-agent, tried in order by `send_message`:
- The sub-agent's turn is still in flight: `steer_into_live_run` injects the
  message into the live pydantic-ai run via `RunContext.enqueue()`
  — the exact mechanism the main agent already uses for mid-turn steering.
  `_execution_loop` already sets `active_run_context` on every sub-agent's
  `BufferedUI` via a UI-agnostic `setattr`; nothing previously read it back.
- The sub-agent's turn has already finished: the message queues, and (if the
  session is idle) a continuation run starts immediately, continuing that
  same persona's conversation from its accumulated history.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from zrb.config.config import CFG
from zrb.llm.agent.activity import agent_activity_registry
from zrb.llm.agent.run.authority_snapshot import (
    AuthoritySnapshot,
    capture_current_authority,
)
from zrb.llm.agent.run.runner import run_agent
from zrb.llm.config.limiter import llm_limiter
from zrb.llm.ui.base.message_queue import steer_into_live_run

if TYPE_CHECKING:
    from zrb.llm.agent.subagent.manager import SubAgentManager
    from zrb.llm.ui.buffered_ui import BufferedUI


@dataclass
class LiveSubAgentSession:
    """One delegated sub-agent's live, in-memory conversation state."""

    agent_id: str
    agent_name: str
    session_id: str
    sub_agent_manager: "SubAgentManager"
    buffered_ui: "BufferedUI"
    # The run_scope the original delegation turn ran under (see delegate.py's
    # comment on why it's a fresh uuid4, not the display-only agent_id).
    # Continuations must reuse it — a fresh scope per turn would make
    # file_observation.py forget what earlier turns of this same sub-agent
    # conversation already read.
    run_scope: str = field(default_factory=lambda: uuid.uuid4().hex)
    # What the original delegation was actually granted (permission policy,
    # yolo, sandbox), captured while its scope was still bound. A
    # continuation runs long after that scope has exited, so it must rebind
    # this explicitly rather than inherit whatever is ambient at that later,
    # unrelated point — see `authority_snapshot.py`'s module docstring.
    authority: "AuthoritySnapshot | None" = None
    history: list = field(default_factory=list)
    pending_queue: list[str] = field(default_factory=list)
    state: str = "idle"  # "idle" | "running"
    # The asyncio.Task currently driving this session's run — a continuation
    # spawned by `send_message`, or the original delegate turn's own task (set
    # by `run_agent_task`). `cancel` uses it to stop what the sub-agent is
    # doing (Esc while viewing in the TUI).
    active_task: "asyncio.Task | None" = None
    # True only between `cancel` and the cancelled task's own handling of the
    # CancelledError. Lets `run_agent_task` tell a human-initiated cancel
    # from the main run's own cancellation, and swallow only the former so the
    # main agent's turn survives a sub-agent cancel in a fan-out.
    cancelled_by_human: bool = False
    # Sticky record that a human cancelled this session (Esc while viewing).
    # Unlike `cancelled_by_human` it is never reset by a new continuation, so
    # `_continue_live_session` can tell that the main agent only ever heard
    # "Cancelled by user" from this delegation and must be handed the
    # continuation's latest response on its natural end
    # (`_report_latest_response_to_parent`).
    notify_parent_on_end: bool = False

    def set_active_task(self, task: "asyncio.Task | None") -> None:
        """Set the task driving this session's run, if any."""
        self.active_task = task

    def consume_cancelled_flag(self) -> bool:
        """Read-and-reset the human-cancel flag (see `cancelled_by_human`)."""
        flag = self.cancelled_by_human
        self.cancelled_by_human = False
        return flag


class LiveSubAgentSessionRegistry:
    """Tracks live sub-agent sessions per chat session_id, mirroring
    `agent_activity_registry`'s session-scoping so multi-session use (the web
    runner) never bleeds one session's sub-agents into another's."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, LiveSubAgentSession]] = {}

    def add_session(
        self,
        session_id: str,
        agent_id: str,
        agent_name: str,
        sub_agent_manager: "SubAgentManager",
        buffered_ui: "BufferedUI",
        yolo_override: bool | None = None,
    ) -> LiveSubAgentSession:
        """Register a live session, capturing the caller's current authority.

        Called synchronously from `run_agent_task` while the delegating
        turn's own scope is still bound, so `capture_current_authority` sees
        the real grant — not whatever is ambient whenever a later
        continuation happens to run (see `authority_snapshot.py`).
        `yolo_override` is the same per-call override `run_agent_task` passes
        to its own `run_agent()` call for the original turn.
        """
        entry = LiveSubAgentSession(
            agent_id=agent_id,
            agent_name=agent_name,
            session_id=session_id,
            sub_agent_manager=sub_agent_manager,
            buffered_ui=buffered_ui,
            authority=capture_current_authority(yolo_override),
        )
        self._sessions.setdefault(session_id, {})[agent_id] = entry
        return entry

    def get(self, session_id: str, agent_id: str) -> "LiveSubAgentSession | None":
        return self._sessions.get(session_id, {}).get(agent_id)

    def active(self, session_id: str) -> list[LiveSubAgentSession]:
        """Every tracked session for *session_id* — running and finished
        alike, ordered by registration. The picker's data source: a finished
        sub-agent stays selectable for the rest of the chat session."""
        return list(self._sessions.get(session_id, {}).values())

    def mark_turn_finished(self, session_id: str, agent_id: str, history: list) -> None:
        """Record the just-finished turn's resulting history and go idle."""
        entry = self.get(session_id, agent_id)
        if entry is None:
            return
        entry.history = history
        entry.state = "idle"

    async def send_message(self, session_id: str, agent_id: str, text: str) -> bool:
        """Deliver *text* to the sub-agent *agent_id*: inject it live if its
        turn is currently in flight, otherwise queue it (starting a
        continuation immediately if the session is idle).

        Returns False only when no such session is registered — the caller
        (a human navigating the TUI) should never see this for an entry the
        picker itself listed.
        """
        entry = self.get(session_id, agent_id)
        if entry is None:
            return False
        run_context = getattr(entry.buffered_ui, "active_run_context", None)
        if steer_into_live_run(run_context, text, []):
            return True
        entry.pending_queue.append(text)
        if entry.state == "idle":
            # Claimed synchronously, before spawning: the check-then-spawn is
            # not separated by an `await`, so two messages arriving back to
            # back cannot both see "idle" and double-spawn a continuation.
            entry.state = "running"
            entry.cancelled_by_human = False  # a fresh run, not a stale flag
            entry.active_task = asyncio.ensure_future(_continue_live_session(entry))
        return True

    def cancel(self, session_id: str, agent_id: str) -> bool:
        """Cancel what the sub-agent is doing: drop its queued messages and
        cancel its current run task (continuation or original delegation).

        Returns False when no such session is tracked, or when it had nothing
        in flight to cancel — the caller decides whether to report it.

        The run task's own code (``run_agent_task``) swallows the resulting
        CancelledError and returns a "cancelled" result, so cancelling one
        sub-agent of a fan-out does not take down the main agent's turn that
        is awaiting the delegation.
        """
        entry = self.get(session_id, agent_id)
        if entry is None:
            return False
        had_work = bool(entry.pending_queue)
        entry.pending_queue.clear()
        task = entry.active_task
        entry.active_task = None
        if task is not None and not task.done():
            entry.cancelled_by_human = True
            task.cancel()
            had_work = True
        entry.state = "idle"
        if had_work:
            # The main agent only ever heard "Cancelled by user" from this
            # delegation. If the session is continued, its final reply must be
            # pushed back so the main agent learns what it produced.
            entry.notify_parent_on_end = True
        return had_work

    def clear(self, session_id: str | None = None) -> None:
        """Clear one session's entries, or every session's when *session_id*
        is omitted (e.g. process-lifetime teardown)."""
        if session_id is None:
            self._sessions.clear()
        else:
            self._sessions.pop(session_id, None)

    def tracked_session_count(self) -> int:
        """How many distinct session_ids this registry currently holds a
        bucket for. Mirrors `AgentActivityRegistry.tracked_session_count` —
        the same "did teardown actually release it" check a test needs,
        since `active()` alone cannot distinguish "no bucket" from "an empty
        bucket"."""
        return len(self._sessions)


live_subagent_session_registry = LiveSubAgentSessionRegistry()


async def _continue_live_session(entry: LiveSubAgentSession) -> None:
    """Drain `entry.pending_queue` by running a fresh turn per message,
    continuing the same sub-agent persona's conversation from its
    accumulated history.

    Callers must set ``entry.state = "running"`` before spawning this (see
    `send_message`) — that assignment is what prevents a second concurrent
    continuation for the same entry, so this function itself holds no lock.
    """
    try:
        while entry.pending_queue:
            text = entry.pending_queue.pop(0)
            agent = entry.sub_agent_manager.create_agent(entry.agent_name)
            if agent is None:
                # The definition disappeared mid-session (reload, removal) --
                # nothing sane to continue with. Drop this message and keep
                # draining the rest rather than looping forever on it.
                CFG.LOGGER.debug(
                    f"Cannot continue live session for '{entry.agent_name}': "
                    "its definition no longer resolves."
                )
                continue
            # Reflected in the compact main-view activity line while this
            # continuation runs, same as the sub-agent's original turn was.
            agent_activity_registry.start(
                entry.agent_id, entry.agent_name, task=text, session_id=entry.session_id
            )
            try:
                # The reply is not surfaced anywhere else -- the human watches it
                # stream via `entry.buffered_ui` directly (no tool call is
                # waiting on a return value here, unlike a normal delegation).
                # Rebind the original delegation's captured authority
                # explicitly — this call runs long after that scope exited,
                # so ambient inheritance alone would pick up whatever is
                # current at this later point instead (see
                # authority_snapshot.py). Passing these as explicit arguments
                # is sufficient: run_agent resolves and binds each of them
                # itself (its own ExitStack), regardless of what is ambient
                # at the call site.
                authority = entry.authority
                _result, history = await run_agent(
                    agent=agent,
                    message=text,
                    message_history=entry.history,
                    limiter=llm_limiter,
                    ui=entry.buffered_ui,
                    run_scope=entry.run_scope,
                    permission_policy=(
                        authority.permission_policy if authority else None
                    ),
                    yolo=authority.yolo if authority else None,
                    sandbox_policy=authority.sandbox_policy if authority else None,
                )
                entry.history = history
            except Exception as e:  # noqa: BLE001
                CFG.LOGGER.debug(
                    f"Live sub-agent continuation for '{entry.agent_name}' failed: {e}"
                )
            finally:
                if entry.active_task is asyncio.current_task():
                    entry.active_task = None
                agent_activity_registry.finish(
                    entry.agent_id, session_id=entry.session_id
                )
    finally:
        # The loop can be cut short before its trailing assignment: `cancel()`
        # (Esc while viewing) cancels this task, and CancelledError is not an
        # `Exception` so it would skip the plain `except` above. The session
        # must still come back to "idle" or a later message would queue forever
        # behind a stuck "running" state. `cancel()` also sets it, but this
        # guards every other path (loop teardown, unexpected task death).
        entry.state = "idle"
        # The session ended (its queue drained, or a cancel cut it short).
        # Mark the end in the live view — unless a human cancelled it, in
        # which case the TUI already wrote "<Esc> Canceled" via
        # `cancel_viewed_agent`, and a "<Done>" on top would contradict it. A
        # session that was cancelled and then continued also hands its latest
        # response to the main agent, which only ever heard "Cancelled by
        # user" from it; a second cancel suppresses both.
        if not entry.cancelled_by_human:
            entry.buffered_ui.append_to_output("<Done>")
            if entry.notify_parent_on_end:
                _report_latest_response_to_parent(entry)


def _report_latest_response_to_parent(entry: LiveSubAgentSession) -> None:
    """Hand a cancelled-then-continued sub-agent's latest response to the main agent.

    The main agent last heard "Cancelled by user" from this delegation; the
    continuation's output only ever streamed into the sub-agent's own live
    view. On the session's natural end, submit just the continuation's latest
    response (extracted from the accumulated history) through the parent UI,
    which steers it into the live main turn or queues it as the next one.
    Best-effort: a missing parent UI, an empty history, or a delivery failure
    must not break the drain.
    """
    parent = getattr(entry.buffered_ui, "parent_ui", None)
    if parent is None or not hasattr(parent, "submit_message"):
        return
    # lazy: zrb.llm.util.history_formatter transitively loads pydantic_ai.
    from zrb.llm.util.history_formatter import extract_last_response_text

    latest_response = extract_last_response_text(entry.history)
    if not latest_response:
        return
    try:
        parent.submit_message(latest_response)
    except Exception as e:  # noqa: BLE001
        CFG.LOGGER.debug(
            f"Failed to report '{entry.agent_name}' continuation to main agent: {e}"
        )
