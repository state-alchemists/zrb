"""
LLM Hook Examples

This demonstrates various ways to use hooks with zrb's LLM chat.

Hook Events:
- SESSION_START: Fired when a session begins
- SESSION_END: Fired before a session ends (can extend session)
- USER_PROMPT_SUBMIT: Fired when user submits a prompt
- PRE_TOOL_USE: Fired before tool execution (can block/deny)
- POST_TOOL_USE: Fired after successful tool execution
- POST_TOOL_USE_FAILURE: Fired after failed tool execution
- NOTIFICATION: Fired on system notifications
- STOP: Fired when session is stopped (Ctrl+C)
- PRE_COMPACT: Fired before history compaction
"""

from zrb import llm_chat
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.types import HookEvent

# =============================================================================
# Example 1: Simple Logging Hook
# =============================================================================


async def logging_hook(context: HookContext) -> HookResult:
    """Log all hook events to console.

    This is a "global" hook - runs on all events.
    """
    print(f"[LOG] Event: {context.event.value}")
    if context.tool_name:
        print(f"[LOG]   Tool: {context.tool_name}")
    if context.prompt:
        print(f"[LOG]   Prompt: {context.prompt[:100]}...")
    return HookResult()  # No modification, just logging


# =============================================================================
# Example 2: Session Tracker Hook
# =============================================================================


class SessionTrackerHook:
    """Track session state across events.

    Demonstrates stateful hooks that maintain data between events.
    """

    def __init__(self):
        self.session_id: str | None = None
        self.tool_calls: list[str] = []
        self.prompts: list[str] = []

    async def __call__(self, context: HookContext) -> HookResult:
        if context.event == HookEvent.SESSION_START:
            self.session_id = context.session_id
            self.tool_calls = []
            self.prompts = []
            print(f"[SESSION] Started: {self.session_id}")

        elif context.event == HookEvent.USER_PROMPT_SUBMIT:
            if context.prompt:
                self.prompts.append(context.prompt)
            print(f"[SESSION] Prompt #{len(self.prompts)}")

        elif context.event == HookEvent.POST_TOOL_USE:
            if context.tool_name:
                self.tool_calls.append(context.tool_name)
            print(f"[SESSION] Tool #{len(self.tool_calls)}: {context.tool_name}")

        elif context.event == HookEvent.SESSION_END:
            print(f"[SESSION] Ended: {self.session_id}")
            print(f"[SESSION]   Prompts: {len(self.prompts)}")
            print(f"[SESSION]   Tool calls: {len(self.tool_calls)}")
            print(f"[SESSION]   Tools used: {set(self.tool_calls)}")

        return HookResult()


# =============================================================================
# Example 3: Tool Permission Hook
# =============================================================================


async def permission_hook(context: HookContext) -> HookResult:
    """Control tool permissions.

    Demonstrates PRE_TOOL_USE hook that can allow/deny/ask.
    """
    if context.event != HookEvent.PRE_TOOL_USE:
        return HookResult()

    # Tool name is available in context.tool_name
    tool_name = context.tool_name or ""

    # Dangerous tools - always deny
    DANGEROUS_TOOLS = {"Bash"}  # Add more as needed

    # Safe tools - always allow
    SAFE_TOOLS = {"Read", "Glob", "LS", "Grep"}

    if tool_name in DANGEROUS_TOOLS:
        # Check if command looks safe
        tool_input = context.tool_input or {}
        command = tool_input.get("command", "")

        # Allow read-only commands
        safe_patterns = ["ls", "cat", "grep", "find", "git status", "git log"]
        if any(cmd in command for cmd in safe_patterns):
            print(f"[PERMISSION] Allowing safe Bash: {command[:50]}")
            return HookResult.allow(
                permission_decision="allow", reason="Command appears to be read-only"
            )

        # Block dangerous patterns
        dangerous_patterns = ["rm ", "rmdir", "sudo", "chmod", "chown", ">"]
        if any(pat in command for pat in dangerous_patterns):
            print(f"[PERMISSION] Blocking dangerous Bash: {command[:50]}")
            return HookResult.deny(
                reason=f"Command contains dangerous pattern: {command}"
            )

        # Ask for everything else
        print(f"[PERMISSION] Asking about Bash: {command[:50]}")
        return HookResult.ask(reason=f"Please confirm: {command}")

    if tool_name in SAFE_TOOLS:
        print(f"[PERMISSION] Auto-allowing safe tool: {tool_name}")
        return HookResult.allow(
            permission_decision="allow", reason=f"{tool_name} is a safe read-only tool"
        )

    # Unknown tool - ask
    return HookResult.ask(reason=f"Unknown tool: {tool_name}")


# =============================================================================
# Example 4: Journal Reminder Hook
# =============================================================================


class JournalReminderHook:
    """Remind LLM to journal at session end.

    Similar to the built-in journaling hook.
    """

    def __init__(self):
        self.had_activity = False
        self.reminder_sent = False

    async def __call__(self, context: HookContext) -> HookResult:
        # Track activity
        if context.event == HookEvent.POST_TOOL_USE:
            self.had_activity = True

        # Send reminder at session end
        if context.event == HookEvent.SESSION_END:
            if self.had_activity and not self.reminder_sent:
                self.reminder_sent = True
                return HookResult.with_system_message(
                    "Before ending, consider: Did you learn anything worth documenting? "
                    "If so, update the project notes."
                )

        return HookResult()


# =============================================================================
# Example 5: Command Hook (via JSON/YAML)
# =============================================================================

# Command hooks are defined in hooks.json or hooks.yaml
# They run shell commands and parse JSON output.
#
# See .zrb/hooks.json for examples:
# - Block dangerous Bash commands
# - Log all tool usage
# - Send notifications on errors


# =============================================================================
# Example 6: Response Transformation Hook (replace_response=True)
# =============================================================================


class ResponseTransformerHook:
    """Transform the final response at session end.

    Demonstrates replace_response=True - the extended session's response
    replaces the original response.

    Use cases:
    - Summarize long responses
    - Add metadata or formatting
    - Clean up or sanitize output

    Contrast with journal_reminder (replace_response=False):
    - journal_reminder: Extended session for side effects, original response returned
    - ResponseTransformer: Extended session's response becomes final response
    """

    def __init__(self, max_length: int = 500):
        self.max_length = max_length
        self.response_count = 0

    async def __call__(self, context: HookContext) -> HookResult:
        if context.event != HookEvent.SESSION_END:
            return HookResult()

        # Get the session output from context
        output = context.event_data.get("output", "")
        if not output:
            return HookResult()

        # Only transform long responses
        if len(str(output)) > self.max_length:
            self.response_count += 1
            print(
                f"[TRANSFORM] Response #{self.response_count} is {len(str(output))} chars, summarizing..."
            )
            return HookResult.with_system_message(
                f"The previous response was too long ({len(str(output))} chars). "
                f"Please provide a concise summary under {self.max_length} characters "
                f"while preserving key information.",
                replace_response=True,  # Extended session's response replaces original
            )

        return HookResult()


# =============================================================================
# Register Hooks
# =============================================================================

# Create hook instances
session_tracker = SessionTrackerHook()
journal_reminder = JournalReminderHook()
response_transformer = ResponseTransformerHook(max_length=1000)


def register_hooks(manager):
    """Register all hooks with the manager.

    Called automatically by add_hook_factory().
    """
    # Register session tracker for multiple events
    manager.register(
        session_tracker,
        events=[
            HookEvent.SESSION_START,
            HookEvent.USER_PROMPT_SUBMIT,
            HookEvent.POST_TOOL_USE,
            HookEvent.SESSION_END,
        ],
    )

    # Register permission hook for PRE_TOOL_USE only
    manager.register(permission_hook, events=[HookEvent.PRE_TOOL_USE])

    # Register journal reminder for activity tracking and session end
    # Uses replace_response=False (default) - side effects only
    manager.register(
        journal_reminder,
        events=[
            HookEvent.POST_TOOL_USE,
            HookEvent.SESSION_END,
        ],
    )

    # Register response transformer for SESSION_END
    # Uses replace_response=True - transforms the final response
    # Uncomment to enable:
    # manager.register(
    #     response_transformer,
    #     events=[HookEvent.SESSION_END]
    # )


# Register hooks with llm_chat task
llm_chat.add_hook_factory(register_hooks)


# =============================================================================
# Alternatively: Direct Registration
# =============================================================================

# You can also register hooks directly without a factory:
#
# from zrb.llm.hook.manager import hook_manager
#
# hook_manager.register(logging_hook, events=None)  # Global hook (all events)
# hook_manager.register(my_hook, events=[HookEvent.SESSION_END])

# =============================================================================
# Notes
# =============================================================================

# Hook Execution Order:
# 1. Hooks are sorted by priority (higher first)
# 2. Hooks run sequentially (not parallel)
# 3. If a hook returns should_stop=True, remaining hooks are skipped
# 4. If a hook returns block(), execution is blocked

# Hook Results:
# - HookResult(): Continue normally
# - HookResult.with_system_message(msg): Inject message, return original response
# - HookResult.with_system_message(msg, replace_response=True): Inject message, return extended response
# - HookResult.block(reason): Block execution (exit code 2)
# - HookResult.allow(decision, reason): Allow tool use
# - HookResult.deny(reason): Deny tool use
# - HookResult.ask(reason): Ask user for permission

# SESSION_END System Messages:
# When a SESSION_END hook returns with_system_message(), the session extends:
#
#   # Side effects only (default) - journaling, notifications
#   return HookResult.with_system_message("Journal this")
#   # → Extended session runs, ORIGINAL response returned to user
#
#   # Replace response - summarization, transformation
#   return HookResult.with_system_message("Summarize", replace_response=True)
#   # → Extended session response becomes the FINAL response

# Match Matchers:
# You can filter hooks using matchers:
#
# from zrb.llm.hook.schema import MatcherConfig, HookConfig
#
# hook_config = HookConfig(
#     name="block-bash-rm",
#     events=[HookEvent.PRE_TOOL_USE],
#     type=HookType.COMMAND,
#     config=CommandHookConfig(command="echo 'denied'"),
#     matchers=[
#         MatcherConfig(
#             field="tool_name",
#             operator=MatcherOperator.EQUALS,
#             value="Bash"
#         ),
#         MatcherConfig(
#             field="tool_input.command",
#             operator=MatcherOperator.CONTAINS,
#             value="rm "
#         )
#     ]
# )

# See also:
# - .zrb/hooks.json for JSON-based command hooks
# - .zrb/hooks.yaml for YAML-based command hooks
# - custom_hook.hook.py for Python hook modules
