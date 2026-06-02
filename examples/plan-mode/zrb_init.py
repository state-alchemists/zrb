from zrb import LLMChatTask, cli
from zrb.llm.permission import (
    ALLOW,
    DENY,
    Capability,
    PermissionPolicy,
    Rule,
)

# 1. Define a base permission policy (Plan Mode adds its own restrictions on top)
base_policy = PermissionPolicy(
    (
        # Deny editing any .env files even outside plan mode
        Rule("Edit", DENY, arg_pattern="**/.env"),
        # Allow reads by default
        Rule(Capability.READ, ALLOW),
    )
)

# 2. Create an LLMChatTask with the policy
safe_explorer = LLMChatTask(
    name="safe-explorer",
    permissions=base_policy,
    ui_greeting=(
        "Hello! I'm operating with Plan Mode support. "
        "Type /plan or press Ctrl+P to enter read-only discovery mode. "
        "Try asking me to read files or explore the codebase."
    ),
)

# 3. Register the task
cli.add_task(safe_explorer)
