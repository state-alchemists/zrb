"""The roster of sub-agents: discovery, registration, agent construction.

`SubAgentManager` scans the agent directories on first use, holds registrations
and builds an agent by name; `sub_agent_manager` is the instance every caller
shares, and `SubAgentDefinition` is the declaration it resolves. The other
modules here hold its parts — loading and search — and the names below are the
public surface, unchanged from the module this replaced.
"""

from zrb.llm.subagent.manager.manager import (
    SubAgentDefinition,
    SubAgentManager,
    sub_agent_manager,
)

__all__ = [
    "SubAgentDefinition",
    "SubAgentManager",
    "sub_agent_manager",
]
