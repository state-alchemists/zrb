"""Live registry of running sub-agents, surfaced as a status panel.

Mirrors the state model opencode/Claude expose (see ADR note in the chat
lifecycle doc): the *what is running* is tracked separately from the text
stream, so any UI backend can render it however it can.

The parent UI's render loop and a sub-agent's run coroutine live in different
asyncio tasks, so this is a process-global singleton rather than a ContextVar
(which copies per task and would not be shared across them).

ponytail: one registry per process. If a single process ever hosts multiple
independent chat sessions (multi-tenant web), key entries by session id to
avoid cross-session bleed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class HasActivityTracking(Protocol):
    """A UI implementation that can feed the sub-agent activity panel.

    ``BufferedUI`` (see ``zrb.llm.tool.delegate``) is the canonical
    implementation; the protocol enables ``isinstance`` checks in
    ``_run_agent_task`` without coupling to a concrete class.
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
    """Tracks currently-running sub-agents for the activity panel.

    Entries are dropped on finish: the panel shows only what is running now and
    self-clears, while each agent's full result is already flushed to the output.
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentActivity] = {}
        self._counter = 0

    def start(self, agent_id: str, name: str, task: str = "") -> int:
        """Track a sub-agent and return its display ordinal (#1, #2, ...)."""
        self._counter += 1
        self._agents[agent_id] = AgentActivity(
            agent_id=agent_id, name=name, ordinal=self._counter, task=task.strip()
        )
        return self._counter

    def update(self, agent_id: str, text: str) -> None:
        agent = self._agents.get(agent_id)
        if agent is None:
            return
        for line in reversed(text.splitlines()):
            if line.strip():
                agent.last_line = line.strip()
                return

    def finish(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)
        # Restart numbering once the batch fully drains, so the next fan-out
        # begins at #1 instead of an ever-growing count.
        if not self._agents:
            self._counter = 0

    def active(self) -> list[AgentActivity]:
        return list(self._agents.values())

    def snapshot(self) -> list[dict[str, object]]:
        """Serializable view for non-TUI backends (web/polling poll responses)."""
        return [
            {
                "agent_id": a.agent_id,
                "name": a.name,
                "ordinal": a.ordinal,
                "task": a.task,
                "last_line": a.last_line,
            }
            for a in self._agents.values()
        ]

    def clear(self) -> None:
        self._agents.clear()


agent_activity_registry = AgentActivityRegistry()
