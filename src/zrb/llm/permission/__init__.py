"""Permission model: capability tags, rulesets, and ambient mode/policy state.

This package is a leaf (no ``zrb.llm.agent`` imports) so both the low-level tool
wrappers in ``agent/common.py`` and the higher-level runner can consult it
without circular imports.

* ``capability`` — per-tool capability tags (read/edit/execute/network/delegate/meta)
* ``policy``     — ``Rule`` / ``PermissionPolicy`` (allow|ask|deny) + ``PLAN_MODE_POLICY``
* ``state``      — ambient ``current_permission_policy`` and ``current_agent_mode``

Default-off invariant: with no policy set and mode ``DEFAULT``, every consumer
reproduces today's behavior exactly.
"""

from __future__ import annotations

from zrb.llm.permission.capability import Capability, tag, tool_capability
from zrb.llm.permission.policy import (
    ALLOW,
    ASK,
    DENY,
    PLAN_MODE_POLICY,
    PermissionPolicy,
    Rule,
    from_yolo,
    resolve_policy,
)
from zrb.llm.permission.state import (
    AgentMode,
    current_agent_mode,
    current_permission_policy,
    get_current_agent_mode,
    get_current_permission_policy,
    get_effective_policy,
    set_current_agent_mode,
    set_current_permission_policy,
)

__all__ = [
    "Capability",
    "tag",
    "tool_capability",
    "Rule",
    "PermissionPolicy",
    "PLAN_MODE_POLICY",
    "ALLOW",
    "ASK",
    "DENY",
    "from_yolo",
    "resolve_policy",
    "AgentMode",
    "current_permission_policy",
    "current_agent_mode",
    "get_current_permission_policy",
    "set_current_permission_policy",
    "get_current_agent_mode",
    "set_current_agent_mode",
    "get_effective_policy",
]
