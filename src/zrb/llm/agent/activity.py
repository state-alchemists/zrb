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


@dataclass
class AgentActivity:
    agent_id: str
    name: str
    task: str = ""  # the deliverable/task the agent was assigned
    status: str = "running"  # "running" only while tracked; dropped on finish
    last_line: str = ""


class AgentActivityRegistry:
    """Tracks currently-running sub-agents for the activity panel.

    Entries are dropped on finish: the panel shows only what is running now and
    self-clears, while each agent's full result is already flushed to the output.
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentActivity] = {}

    def start(self, agent_id: str, name: str, task: str = "") -> None:
        self._agents[agent_id] = AgentActivity(
            agent_id=agent_id, name=name, task=task.strip()
        )

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

    def active(self) -> list[AgentActivity]:
        return list(self._agents.values())

    def snapshot(self) -> list[dict[str, str]]:
        """Serializable view for non-TUI backends (web/polling poll responses)."""
        return [
            {
                "agent_id": a.agent_id,
                "name": a.name,
                "task": a.task,
                "status": a.status,
                "last_line": a.last_line,
            }
            for a in self._agents.values()
        ]

    def clear(self) -> None:
        self._agents.clear()


agent_activity_registry = AgentActivityRegistry()
