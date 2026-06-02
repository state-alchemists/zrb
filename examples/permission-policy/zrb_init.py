"""
Permission Policy Example

This example demonstrates how to define and apply a PermissionPolicy
for LLMChatTask using a hook factory.

Usage:
    cd examples/permission-policy
    zrb llm chat

Alternatively, set the policy via environment variable:
    export ZRB_LLM_PERMISSIONS="read:allow,edit:ask,execute:ask,*:deny"
    zrb llm chat
"""

from zrb import LLMChatTask, cli
from zrb.llm.permission import (
    ALLOW,
    ASK,
    DENY,
    Capability,
    PermissionPolicy,
    Rule,
)
from zrb.llm.permission.state import set_current_permission_policy

# 1. Define a custom permission policy
my_policy = PermissionPolicy(
    (
        # Deny editing any .env files
        Rule("Edit", DENY, arg_pattern="**/.env"),
        # Allow all read operations
        Rule(Capability.READ, ALLOW),
        # Force confirmation for all shell commands (both tool names)
        Rule("Bash", ASK),
        Rule("Shell", ASK),
        # Deny everything else by default
        Rule("*", DENY),
    )
)


# 2. Create a hook factory that applies the policy at session start
def apply_policy(manager):
    set_current_permission_policy(my_policy)
    return manager


# 3. Create an LLMChatTask with the policy hook
safe_chat = LLMChatTask(
    name="safe-chat",
    ui_greeting="Hello! I'm operating under a strict permission policy. Try asking me to read files, edit .env, or run shell commands.",
)

safe_chat.add_hook_factory(apply_policy)
cli.add_task(safe_chat)
