"""
Plan Mode Example

Shows how Plan Mode works with a permission policy applied via hook factory.

Usage:
    cd examples/plan-mode
    zrb llm chat
"""

from zrb import LLMChatTask, cli
from zrb.llm.permission import (
    ALLOW,
    DENY,
    Capability,
    PermissionPolicy,
    Rule,
)
from zrb.llm.permission.state import set_current_permission_policy

# 1. Define a base permission policy (Plan Mode adds its own restrictions on top)
base_policy = PermissionPolicy(
    (
        # Deny editing any .env files even outside plan mode
        Rule("Edit", DENY, arg_pattern="**/.env"),
        # Allow reads by default
        Rule(Capability.READ, ALLOW),
    )
)


# 2. Create a hook factory that applies the policy at session start
def apply_policy(manager):
    set_current_permission_policy(base_policy)
    return manager


# 3. Create an LLMChatTask
safe_explorer = LLMChatTask(
    name="safe-explorer",
    ui_greeting=(
        "Hello! I'm operating with Plan Mode support. "
        "Type /plan or press Ctrl+P to enter read-only discovery mode. "
        "Try asking me to read files or explore the codebase."
    ),
)
safe_explorer.add_hook_factory(apply_policy)
cli.add_task(safe_explorer)
