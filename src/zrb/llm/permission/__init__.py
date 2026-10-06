"""Permission model: capability tags, rulesets, and ambient mode/policy state.

Leaf package (no ``zrb.llm.agent`` imports). With no policy set and mode
``BUILD``, nothing is constrained.
"""

from __future__ import annotations

from zrb.llm.permission.capability import (
    Capability,
    capability_metadata,
    tag,
    tool_capability,
)
from zrb.llm.permission.observability import record_policy_decision
from zrb.llm.permission.policy import (
    ALLOW,
    ASK,
    DENY,
    PLAN_MODE_POLICY,
    PermissionPolicy,
    PermissionPolicyInput,
    Rule,
    resolve_policy,
)
from zrb.llm.permission.state import (
    AgentMode,
    current_agent_mode,
    current_permission_policy,
    get_current_agent_mode,
    get_current_permission_policy,
    get_effective_policy,
    permission_policy,
    set_current_agent_mode,
)

__all__ = [
    "Capability",
    "capability_metadata",
    "tag",
    "tool_capability",
    "Rule",
    "PermissionPolicy",
    "PermissionPolicyInput",
    "PLAN_MODE_POLICY",
    "ALLOW",
    "ASK",
    "DENY",
    "resolve_policy",
    "AgentMode",
    "current_permission_policy",
    "current_agent_mode",
    "get_current_permission_policy",
    "permission_policy",
    "get_current_agent_mode",
    "set_current_agent_mode",
    "get_effective_policy",
    "record_policy_decision",
]
