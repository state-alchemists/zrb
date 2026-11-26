"""Tool capabilities by LLM-visible name, for the approval cascade.

A deferred `ToolCallPart` carries a name and its arguments and nothing else: the
capability tag lives on the registered callable
(`capabilities/permission/capability.py`), so `tool_capability(part)` answers
`UNKNOWN` for every deferred call. A ruleset keyed on a capability therefore
never matched — `edit:ask` fell through to a later `*:allow`, and a write the
user had gated ran unprompted.

The answer already exists one layer up: the skip decision
(`get_policy_skip_decision`) builds LLM-visible name → capability from the run's
resolved tools — including the per-run ones a static registry cannot know (MCP
servers, sub-agents, memory). This module is where that map is kept, so both
task classes register it when they build the agent and the cascade reads it by
name.

The map is process-global and last writer wins, which is sound because a
capability belongs to the tool and not to the call: `Write` is `EDIT` in every
run. A name nobody registered stays `UNKNOWN`, which every consumer treats
conservatively.
"""

from __future__ import annotations

from collections.abc import Mapping

from zrb.llm.capabilities.permission.capability import Capability

_capabilities: dict[str, Capability] = {}


def register_tool_capabilities(capabilities: Mapping[str, Capability]) -> None:
    """Record the run's LLM-visible name → capability map for the cascade."""
    _capabilities.update(capabilities)


def get_tool_capability(tool_name: str) -> Capability:
    """The capability registered for *tool_name*, or `UNKNOWN` when none was."""
    return _capabilities.get(tool_name, Capability.UNKNOWN)


__all__ = ["get_tool_capability", "register_tool_capabilities"]
