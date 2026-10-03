"""
Permission Policy Example

Demonstrates applying a PermissionPolicy to the built-in `llm_chat` task
(the one `zrb llm chat` runs) via its `permissions` property.

Rules are checked in order; the first match wins.

Usage:
    cd examples/permission-policy
    zrb llm chat

Alternatively, set the policy via environment variable:
    export ZRB_LLM_PERMISSIONS="read:allow,edit:ask,execute:ask,*:deny"
    zrb llm chat
"""

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.permission import (
    ALLOW,
    ASK,
    DENY,
    Capability,
    PermissionPolicy,
    Rule,
)

# Apply a custom permission policy to the built-in chat task.
llm_chat.permissions = PermissionPolicy(
    (
        # Deny editing any .env file. The pattern is matched with fnmatch
        # against the tool's path argument; "*" also spans "/", so "*.env"
        # covers both ".env" and "config/.env" ("**/.env" would miss ".env").
        Rule("Edit", DENY, arg_pattern="*.env"),
        # Allow all read operations
        Rule(Capability.READ, ALLOW),
        # Force confirmation for shell commands
        Rule("Shell", ASK),
        # Deny everything else by default
        Rule("*", DENY),
    )
)
