from zrb import LLMChatTask, cli
from zrb.llm.permission import (
    ALLOW,
    ASK,
    DENY,
    Capability,
    PermissionPolicy,
    Rule,
)

# 1. Define a custom permission policy
my_policy = PermissionPolicy(
    (
        # Deny editing any .env files
        Rule("Edit", DENY, arg_pattern="**/.env"),
        # Allow all read operations
        Rule(Capability.READ, ALLOW),
        # Force confirmation for all shell commands
        Rule("Bash", ASK),
        # Deny everything else by default
        Rule("*", DENY),
    )
)

# 2. Create an LLMChatTask with the policy
safe_chat = LLMChatTask(
    name="safe-chat",
    permissions=my_policy,
    ui_greeting="Hello! I'm operating under a strict permission policy. Try asking me to read files, edit .env, or run shell commands.",
)

# 3. Register the task
cli.add_task(safe_chat)
