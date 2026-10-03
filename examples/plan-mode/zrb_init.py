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

# Apply a base permission policy to the built-in chat task. While Plan Mode is
# active (toggle with /plan or Shift+Tab), its read-only preset replaces this
# policy; this policy applies again once you leave Plan Mode.
llm_chat.permissions = PermissionPolicy(
    (
        # Deny editing any .env file even outside plan mode. fnmatch's "*"
        # spans "/", so "*.env" covers ".env" and "config/.env" alike.
        Rule("Edit", DENY, arg_pattern="*.env"),
        # Allow reads by default
        Rule(Capability.READ, ALLOW),
    )
)
