"""Live registry of running sub-agents, surfaced as a status panel.

Mirrors the state model opencode/Claude expose: the *what is running* is
tracked separately from the text stream, so any UI backend can render it
however it can.

The parent UI's render loop and a sub-agent's run coroutine live in different
asyncio tasks, so this is a process-global singleton rather than a ContextVar
(which copies per task and would not be shared across them).

Entries are keyed by ``session_id`` (defaulting to ``""``, the single-session
CLI case) so a process hosting multiple independent chat sessions — the web
runner, one process serving many browser tabs — doesn't bleed one session's
running sub-agents into another's activity panel/listing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class HasActivityTracking(Protocol):
    """A UI implementation that can feed the sub-agent activity panel.

    ``BufferedUI`` (see ``zrb.llm.tool.delegate``) is the canonical
    implementation; the protocol enables ``isinstance`` checks in
    ``run_agent_task`` without coupling to a concrete class.
    """

    def set_activity_id(self, agent_id: str) -> None: ...
    def set_label(self, prefix: str) -> None: ...
    @property
    def label(self) -> str: ...


@dataclass
class AgentActivity:
    agent_id: str
    name: str
    ordinal: int = 0  # display number; the panel is the legend for output prefixes
    task: str = ""  # the deliverable/task the agent was assigned
    last_line: str = ""


class AgentActivityRegistry:
    """Tracks currently-running sub-agents for the activity panel, per session.

    Entries are dropped on finish: the panel shows only what is running now and
    self-clears, while each agent's full result is already flushed to the output.
    """

    def __init__(self) -> None:
        self._agents: dict[str, dict[str, AgentActivity]] = {}
        self._counters: dict[str, int] = {}

    def start(
        self, agent_id: str, name: str, task: str = "", session_id: str = ""
    ) -> int:
        """Track a sub-agent and return its display ordinal (#1, #2, ...)."""
        counter = self._counters.get(session_id, 0) + 1
        self._counters[session_id] = counter
        self._agents.setdefault(session_id, {})[agent_id] = AgentActivity(
            agent_id=agent_id, name=name, ordinal=counter, task=task.strip()
        )
        return counter

    def update(self, agent_id: str, text: str, session_id: str = "") -> None:
        agent = self._agents.get(session_id, {}).get(agent_id)
        if agent is None:
            return
        for line in reversed(text.splitlines()):
            if line.strip():
                agent.last_line = line.strip()
                return

    def finish(self, agent_id: str, session_id: str = "") -> None:
        bucket = self._agents.get(session_id)
        if bucket is None:
            return
        bucket.pop(agent_id, None)
        # Restart numbering once this session's batch fully drains, so its
        # next fan-out begins at #1 instead of an ever-growing count.
        if not bucket:
            self._counters[session_id] = 0

    def active(self, session_id: str = "") -> list[AgentActivity]:
        return list(self._agents.get(session_id, {}).values())

    def snapshot(self, session_id: str = "") -> list[dict[str, object]]:
        """Serializable view for non-TUI backends (web/polling poll responses)."""
        return [
            {
                "agent_id": a.agent_id,
                "name": a.name,
                "ordinal": a.ordinal,
                "task": a.task,
                "last_line": a.last_line,
            }
            for a in self._agents.get(session_id, {}).values()
        ]

    def clear(self, session_id: str | None = None) -> None:
        """Clear one session's entries, or every session's when *session_id*
        is omitted (e.g. process-lifetime teardown)."""
        if session_id is None:
            self._agents.clear()
            self._counters.clear()
        else:
            self._agents.pop(session_id, None)
            self._counters.pop(session_id, None)

    def tracked_session_count(self) -> int:
        """How many distinct session_ids this registry currently holds a
        bucket for (including sessions with no agent left running).

        A finished session whose bucket was never `clear()`-ed still counts
        here — this is the number a caller (or a test) checks to confirm a
        session's teardown actually released it, since `active()` alone
        cannot distinguish "no bucket" from "an empty bucket"."""
        return len(self._agents)


agent_activity_registry = AgentActivityRegistry()
