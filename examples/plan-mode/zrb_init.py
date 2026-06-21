"""
Plan Mode Example

Shows how Plan Mode works with a permission policy applied to the built-in
`llm_chat` task (the one `zrb llm chat` runs).

Usage:
    cd examples/plan-mode
    zrb llm chat
"""

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.permission import (
    ALLOW,
    DENY,
    Capability,
    PermissionPolicy,
    Rule,
)

# Apply a base permission policy to the built-in chat task. Plan Mode
# (toggle with /plan or Ctrl+P) layers its read-only restrictions on top.
llm_chat.permissions = PermissionPolicy(
    (
        # Deny editing any .env files even outside plan mode
        Rule("Edit", DENY, arg_pattern="**/.env"),
        # Allow reads by default
        Rule(Capability.READ, ALLOW),
    )
)
