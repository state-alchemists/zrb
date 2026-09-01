"""`SubAgentRegistry` — the canonical collection of sub-agent definitions.

A registry is the *source of defaults*: it stores the full set of
sub-agents found by filesystem discovery *plus* everything appended in code, and
answers queries. It does not scan or build agents — that is `SubAgentManager`'s
job. Configure it from `zrb_init.py`:

    from zrb.llm.agent.subagent.registry import sub_agent_registry
    from zrb.llm.agent.subagent.definition import SubAgentDefinition
    sub_agent_registry.add_agent(SubAgentDefinition(name="mine", path=".", ...))

Unlike `SubAgentManager`, the registry holds no tool surface — the tool registry
is shared by `LLMChatTask`/`LLMTask`/`SubAgentManager` through the
`CommonToolHost` protocol and stays on the manager. Here a registry is purely
the definition collection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from zrb.config.config import CFG

if TYPE_CHECKING:
    from zrb.llm.agent.subagent.definition import SubAgentDefinition

AgentSetValue = list["SubAgentDefinition"] | Callable[[], list["SubAgentDefinition"]]


class SubAgentRegistry:
    """The canonical collection of sub-agent definitions.

    Keeps two layers so a scan cannot wipe a registration:

    - *manual* — definitions registered from code (`add_agent`,
      `set_agents`); always wins a name collision.
    - *discovered* — definitions found on disk by `SubAgentManager.scan()`; a
      later scan replaces this layer only.

    Queries merge the two, manual first. `set_agents` replaces the whole
    collection (the clean-slate swap); `remove_agent` drops a name from both
    layers. `set_agents` accepts a deferred callable resolved at query time.
    """

    def __init__(self, agents: list["SubAgentDefinition"] | None = None):
        """Create a sub-agent registry, optionally seeded with *agents*.

        Args:
            agents: Initial manual layer. May be regenerated later with
                `set_agents`; a plain list freezes at set time, while a
                callable stays deferred until the first query.
        """
        self._manual: AgentSetValue = []
        self._discovered: dict[str, SubAgentDefinition] = {}
        if agents is not None:
            self.set_agents(agents)

    def _resolve(self, value: AgentSetValue) -> list["SubAgentDefinition"]:
        return value() if callable(value) else value

    def _effective_manual(self) -> dict[str, SubAgentDefinition]:
        resolved = self._resolve(self._manual)
        return {definition.name: definition for definition in resolved}

    def _effective(self) -> dict[str, SubAgentDefinition]:
        merged = dict(self._discovered)
        merged.update(self._effective_manual())
        return merged

    def add_agent(self, definition: "SubAgentDefinition") -> None:
        """Register *definition* manually. Survives a later scan or reload."""
        self._manual = [*self._resolve(self._manual), definition]

    def remove_agent(self, name: str) -> None:
        """Drop *name* from both the manual and discovered layers."""
        self._manual = [d for d in self._resolve(self._manual) if d.name != name]
        self._discovered.pop(name, None)

    def set_agents(self, agents: AgentSetValue) -> None:
        """Replace the whole collection (manual layer) with *agents*.

        *agents* may be a concrete list or a deferred callable returning one.
        A callable stays unresolved and is re-evaluated at each query.
        """
        self._manual = agents

    def set_discovered(self, agents: list["SubAgentDefinition"]) -> None:
        """Replace the discovered layer (used by `SubAgentManager.scan`).

        Later entries win a name collision, preserving the scan's
        global→project precedence. Manual registrations are untouched.
        """
        self._discovered = {definition.name: definition for definition in agents}

    def clear_discovered(self) -> None:
        """Drop the discovered layer, keeping manual registrations."""
        self._discovered = {}

    def get_agent_definition(self, name: str) -> "SubAgentDefinition | None":
        """Look up one definition by registered name, own name, or path."""
        definition = self._effective().get(name)
        if not definition:
            for candidate in self._effective().values():
                if candidate.name == name or candidate.path == name:
                    definition = candidate
                    break
        if definition and not self._is_visible(definition.name):
            return None
        return definition

    def get_agents(self) -> list["SubAgentDefinition"]:
        """Every visible definition in the effective collection.

        The ``CFG.LLM_AGENTS`` allowlist twin filters only the discovered
        layer; definitions registered manually (`add_agent`, `set_agents`)
        are always visible."""
        return [
            definition
            for definition in self._effective().values()
            if self._is_visible(definition.name)
        ]

    def _is_visible(self, name: str) -> bool:
        """Whether *name* survives the ``LLM_AGENTS`` allowlist twin.

        The twin (ADR-0091) is a coarse filter over the *discovered* layer:
        env names the default agents that stay in the roster. Anything
        registered manually layers on top and is always visible, matching the
        mental model "env sets the baseline; `zrb_init.py` builds on it".
        Read lazily at query time, so env changes take effect on the next
        roster lookup without any startup copy.
        """
        if name in self._effective_manual().keys():
            return True
        allowed = list(CFG.LLM_AGENTS or [])
        return not allowed or name in allowed


sub_agent_registry = SubAgentRegistry()
