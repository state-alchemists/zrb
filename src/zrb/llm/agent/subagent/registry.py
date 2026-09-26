"""`SubAgentRegistry` — the canonical collection of sub-agent definitions (ADR-0090).

Discovered definitions plus everything registered in code; `SubAgentManager`
does the scanning and owns the tool surface. Layer and allowlist semantics are
`LayeredRegistry`'s; the allowlist here is ``CFG.LLM_AGENTS``. Configure it
from `zrb_init.py`:

    from zrb.llm.agent.subagent.registry import sub_agent_registry
    from zrb.llm.agent.subagent.definition import SubAgentDefinition
    sub_agent_registry.add_agent(SubAgentDefinition(name="mine", path=".", ...))
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from zrb.config.config import CFG
from zrb.llm.util.layered_registry import LayeredRegistry

if TYPE_CHECKING:
    from zrb.llm.agent.subagent.definition import SubAgentDefinition

AgentSetValue = list["SubAgentDefinition"] | Callable[[], list["SubAgentDefinition"]]


class SubAgentRegistry:
    """The canonical collection of sub-agent definitions, and the source of defaults."""

    def __init__(self, agents: AgentSetValue | None = None):
        """Create a registry, optionally seeded with *agents*.

        Args:
            agents: Initial manual layer; a plain list freezes at set time, a
                callable stays deferred until each query.
        """
        self._layers: LayeredRegistry[SubAgentDefinition] = LayeredRegistry(
            lambda: CFG.LLM_AGENTS, agents
        )

    def add_agent(self, definition: "SubAgentDefinition") -> None:
        """Register a definition manually; it survives a later scan or reload."""
        self._layers.add_item(definition)

    def remove_agent(self, name: str) -> None:
        """Drop *name* from both the manual and discovered layers."""
        self._layers.remove_item(name)

    def set_agents(self, agents: AgentSetValue) -> None:
        """Replace the manual layer; a callable is re-evaluated at each query."""
        self._layers.set_items(agents)

    def set_discovered(self, agents: list["SubAgentDefinition"]) -> None:
        """Replace the discovered layer (used by `SubAgentManager.scan`)."""
        self._layers.set_discovered(agents)

    def clear_discovered(self) -> None:
        """Drop the discovered layer, keeping manual registrations."""
        self._layers.clear_discovered()

    def get_agent_definition(self, name: str) -> "SubAgentDefinition | None":
        """Look up one visible entry by registered name, own name, or path."""
        return self._layers.get_item(name)

    def get_agents(self) -> list["SubAgentDefinition"]:
        """Every visible entry; manual wins on collisions."""
        return self._layers.get_items()


sub_agent_registry = SubAgentRegistry()
