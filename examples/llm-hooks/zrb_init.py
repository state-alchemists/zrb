"""
LLM Hook Examples

This demonstrates various ways to use hooks with zrb's LLM chat.

Hook Events:
- SESSION_START: Chat session begins. source is startup (fresh) or resume (continued)
- USER_PROMPT_SUBMIT: Before the LLM processes text (can block)
- PRE_COMMAND: Before a UI command runs (can block)
- POST_COMMAND: After a UI command runs
- PRE_TOOL_USE: Before every tool call (permissionDecision deny/allow/ask/defer; rewrite args)
- POST_TOOL_USE: After a tool succeeds (can block, replace output)
- POST_TOOL_USE_FAILURE: After a tool raises
- PERMISSION_REQUEST: Tool reaches interactive approval (can auto-resolve)
- NOTIFICATION: System notifications
- STOP: Turn finishes — per-turn extension and block-to-continue point
- PRE_COMPACT: Before history summarization (can inject context OR block compaction)
- SESSION_END: Terminal — fires once when chat session ends (matches on `source`)

Any event can also request `continue: false` to halt the whole run (distinct
from a per-event block); on UserPromptSubmit/Stop it ends the turn.
"""

from zrb.builtin.llm.chat import llm_chat
from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.types import HookEvent

# =============================================================================
# Example 1: Simple Logging Hook
# =============================================================================


async def logging_hook(context: HookContext) -> HookResult:
    """Log all hook events to console.

    This is a "global" hook — runs on all events.
    """
    print(f"[LOG] Event: {context.event.value}")
    if context.tool_name:
        print(f"[LOG]   Tool: {context.tool_name}")
    if context.prompt:
        print(f"[LOG]   Prompt: {context.prompt[:100]}...")
    return HookResult()


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
            # `source` is the Claude-compatible matcher field for SessionEnd.
            print(f"[SESSION] Ended: {self.session_id} (source={context.source})")
            print(f"[SESSION]   Prompts: {len(self.prompts)}")
            print(f"[SESSION]   Tool calls: {len(self.tool_calls)}")
            print(f"[SESSION]   Tools used: {set(self.tool_calls)}")

        return HookResult()


# =============================================================================
# Example 3: Tool Permission Hook (PreToolUse)
# =============================================================================


async def permission_hook(context: HookContext) -> HookResult:
    """Control tool permissions via PreToolUse.

    Demonstrates all four `permissionDecision` values:
    - "deny"  — block dangerous tools
    - "allow" — auto-approve safe tools (skip the prompt)
    - "ask"   — force the interactive prompt, overriding any tool-policy/YOLO
                auto-approve (an explicit DENY still wins)
    - "defer" — no opinion; let the normal approval flow decide (== HookResult())
    Plus rewriting tool arguments via updatedInput (see arg_rewrite_hook).
    """
    if context.event != HookEvent.PRE_TOOL_USE:
        return HookResult()

    tool_name = context.tool_name or ""

    SAFE_TOOLS = {"Read", "Glob", "Grep", "LS", "LspListServers"}
    DANGEROUS_TOOLS = {"Bash", "RunShellCommand"}

    if tool_name in DANGEROUS_TOOLS:
        tool_input = context.tool_input or {}
        command = str(tool_input.get("command", tool_input.get("cmd", "")))

        # Allow read-only commands
        safe_patterns = ["ls", "cat", "grep", "find", "git status", "git log"]
        if any(cmd in command for cmd in safe_patterns):
            print(f"[PERMISSION] Allowing safe Bash: {command[:50]}")
            return HookResult(
                success=True,
                modifications={"permissionDecision": "allow"},
            )

        # Deny dangerous patterns
        dangerous_patterns = ["rm ", "rmdir", "sudo", "chmod", "chown", ">"]
        if any(pat in command for pat in dangerous_patterns):
            print(f"[PERMISSION] Blocking dangerous Bash: {command[:50]}")
            return HookResult(
                success=True,
                modifications={"permissionDecision": "deny"},
            )

        # Medium-risk commands: force a prompt even if a tool policy or YOLO
        # would otherwise auto-approve. "ask" overrides those auto-allows.
        ask_patterns = ["git push", "npm install", "pip install", "git commit"]
        if any(pat in command for pat in ask_patterns):
            print(f"[PERMISSION] Forcing prompt for: {command[:50]}")
            return HookResult(
                success=True,
                modifications={"permissionDecision": "ask"},
            )

        # Everything else: defer (no opinion) — equivalent to HookResult().
        return HookResult(
            success=True,
            modifications={"permissionDecision": "defer"},
        )

    if tool_name in SAFE_TOOLS:
        print(f"[PERMISSION] Auto-allowing safe tool: {tool_name}")
        return HookResult(
            success=True,
            modifications={"permissionDecision": "allow"},
        )

    return HookResult()


# =============================================================================
# Example 4: Argument Rewriting Hook (PreToolUse)
# =============================================================================


async def arg_rewrite_hook(context: HookContext) -> HookResult:
    """Rewrite tool arguments before execution.

    Demonstrates updatedInput — the tool sees the rewritten args,
    not the original ones.
    """
    if context.event != HookEvent.PRE_TOOL_USE:
        return HookResult()

    tool_name = context.tool_name or ""

    # Always scope Grep/LS to the project root
    if tool_name in {"Grep", "LS"}:
        tool_input = context.tool_input or {}
        if "path" in tool_input and tool_input["path"] in {"", ".", "/"}:
            print(f"[REWRITE] Scoping {tool_name} to current directory")
            return HookResult(
                success=True,
                modifications={
                    "updatedInput": {"path": "."},
                },
            )

    return HookResult()


# =============================================================================
# Example 5: Journal Reminder Hook (Stop — turn extension)
# =============================================================================


class JournalReminderHook:
    """Remind LLM to journal at each turn end.

    Uses Stop (not SessionEnd — SessionEnd is now terminal, fires once).
    systemMessage turn-extension with replace_response=False (default)
    means the user sees the original response; journaling is a side effect.
    """

    def __init__(self):
        self.had_activity = False

    async def __call__(self, context: HookContext) -> HookResult:
        if context.event == HookEvent.POST_TOOL_USE:
            self.had_activity = True

        if context.event == HookEvent.STOP and self.had_activity:
            self.had_activity = False
            return HookResult(
                success=True,
                modifications={
                    "systemMessage": (
                        "Review the turn for learnings worth documenting. "
                        "Update any relevant notes."
                    ),
                },
            )

        return HookResult()


# =============================================================================
# Example 6: Response Transformation Hook (Stop — replace_response=True)
# =============================================================================


class ResponseTransformerHook:
    """Transform long responses at turn end using Stop.

    Demonstrates replace_response=True — the extended turn's response
    replaces the original.

    Must be on Stop (SessionEnd is terminal; it only fires at chat exit).
    """

    def __init__(self, max_length: int = 500):
        self.max_length = max_length
        self.response_count = 0

    async def __call__(self, context: HookContext) -> HookResult:
        if context.event != HookEvent.STOP:
            return HookResult()

        output = context.event_data.get("output", "")
        if not output:
            return HookResult()

        if len(str(output)) > self.max_length:
            self.response_count += 1
            print(
                f"[TRANSFORM] Response #{self.response_count} is "
                f"{len(str(output))} chars, summarizing..."
            )
            return HookResult(
                success=True,
                modifications={
                    "systemMessage": (
                        f"The previous response was too long "
                        f"({len(str(output))} chars). "
                        f"Please provide a concise summary under "
                        f"{self.max_length} characters "
                        f"while preserving key information."
                    ),
                    "replaceResponse": True,
                },
            )

        return HookResult()


# =============================================================================
# Example 7: PostToolUse — Block or Replace Tool Results
# =============================================================================


async def tool_result_hook(context: HookContext) -> HookResult:
    """Inspect and optionally block or rewrite tool results.

    Demonstrates PostToolUse blocking and updatedToolOutput.
    """
    if context.event == HookEvent.POST_TOOL_USE:
        tool_name = context.tool_name or ""
        tool_result = context.event_data.get("result", {})

        # Block empty search results — let the model know
        if tool_name in {"Grep", "SearchFiles"}:
            result_content = str(tool_result.get("content", ""))
            if "no matches" in result_content.lower() or not result_content.strip():
                return HookResult.block(reason="No results found, try a broader query")

        # Redact sensitive patterns from file reads
        if tool_name == "Read":
            result_content = str(tool_result.get("content", ""))
            if any(
                sensitive in result_content
                for sensitive in ["API_KEY", "PASSWORD", "SECRET"]
            ):
                censored = result_content
                for word in ["API_KEY", "PASSWORD", "SECRET"]:
                    censored = censored.replace(word, "[REDACTED]")
                return HookResult(
                    success=True,
                    modifications={
                        "hookSpecificOutput": {
                            "updatedToolOutput": censored,
                        },
                    },
                )

    return HookResult()


# =============================================================================
# Example 8: UserPromptSubmit — Block Inappropriate Prompts
# =============================================================================


async def prompt_gate_hook(context: HookContext) -> HookResult:
    """Block prompts that match certain patterns.

    UserPromptSubmit hooks fire before the LLM processes text.
    A block returns the reason to the user without invoking the model.
    """
    if context.event != HookEvent.USER_PROMPT_SUBMIT:
        return HookResult()

    prompt = context.prompt or ""

    blocked_patterns = [
        "delete everything",
        "remove all files",
    ]
    for pattern in blocked_patterns:
        if pattern in prompt.lower():
            print(f"[GATE] Blocked prompt containing: {pattern}")
            return HookResult.block(reason=f"Prompt blocked: contains '{pattern}'")

    return HookResult()


# =============================================================================
# Example 9: PreCompact — Inject Context Before Summarization
# =============================================================================


async def precompact_hook(context: HookContext) -> HookResult:
    """Inject context before history summarization.

    PreCompact fires with trigger="auto" before zrb summarizes
    old turns. This hook can inject additionalContext to preserve
    important information the model might otherwise lose.
    """
    if context.event != HookEvent.PRE_COMPACT:
        return HookResult()

    token_count = context.event_data.get("token_count", 0)
    message_count = context.event_data.get("message_count", 0)
    print(f"[COMPACT] About to compact {message_count} msgs ({token_count} tokens)")

    # PreCompact can also BLOCK compaction — skip summarization for this turn so
    # the full history is preserved (the hard context-window prune still applies
    # as a safety net). Uncomment to enable:
    #   return HookResult.block(reason="Preserve full history this turn")

    # Otherwise: inject context to preserve before summarization.
    return HookResult(
        success=True,
        modifications={
            "hookSpecificOutput": {
                "additionalContext": (
                    "Preserve these project conventions: "
                    "Python 3.14, async/await, pytest."
                ),
            },
        },
    )


# =============================================================================
# Example 10: PreCommand — Rewrite Command Arguments
# =============================================================================


async def command_rewrite_hook(context: HookContext) -> HookResult:
    """Rewrite or block UI commands before they execute.

    Demonstrates PreCommand argument rewriting via updatedInput.
    """
    if context.event != HookEvent.PRE_COMMAND:
        return HookResult()

    cmd_name = context.command_name or ""
    cmd_args = context.command_args or ""

    # Always redirect /help to the topic form
    if cmd_name == "/help" and not cmd_args:
        print("[CMD] Rewriting bare /help to /help hooks")
        return HookResult(
            success=True,
            modifications={"command_args": "hooks"},
        )

    return HookResult()


# =============================================================================
# Example 11: PostCommand — Observe Command Results
# =============================================================================


async def command_audit_hook(context: HookContext) -> HookResult:
    """Audit UI command execution.

    PostCommand fires after a command completes. command_handled
    indicates whether zrb processed it or passed it to the model.
    """
    if context.event != HookEvent.POST_COMMAND:
        return HookResult()

    cmd_name = context.command_name or ""
    cmd_handled = context.event_data.get("command_handled", False)

    print(f"[AUDIT] Command: {cmd_name}, handled: {cmd_handled}")

    return HookResult()


# =============================================================================
# Example 12: PostToolUseFailure — Handle Tool Errors
# =============================================================================


async def error_log_hook(context: HookContext) -> HookResult:
    """Log and handle tool execution failures.

    PostToolUseFailure fires when a tool raises. The error context
    field contains the exception message.
    """
    if context.event != HookEvent.POST_TOOL_USE_FAILURE:
        return HookResult()

    tool_name = context.tool_name or ""
    error = context.event_data.get("error", str(context.error or ""))

    print(f"[ERROR] Tool {tool_name} failed: {error}")

    return HookResult()


# =============================================================================
# Example 13: PermissionRequest — Auto-Resolve Approval
# =============================================================================


async def auto_approve_hook(context: HookContext) -> HookResult:
    """Auto-approve or auto-deny permission requests.

    PermissionRequest fires when a tool reaches interactive approval.
    Resolve via hookSpecificOutput.decision.behavior.
    """
    if context.event != HookEvent.PERMISSION_REQUEST:
        return HookResult()

    tool_name = context.tool_name or ""
    suggestions = context.event_data.get("permission_suggestions", "")

    # Auto-approve known safe operations
    SAFE_PATTERNS = ["git status", "git log", "ls -la"]
    if any(p in suggestions for p in SAFE_PATTERNS):
        print(f"[APPROVE] Auto-approving: {tool_name}")
        return HookResult(
            success=True,
            modifications={
                "hookSpecificOutput": {
                    "decision": {"behavior": "allow"},
                },
            },
        )

    # Let everything else go to interactive approval
    return HookResult()


# =============================================================================
# Example 14: Notification — Handle LLM Notifications
# =============================================================================


async def notification_handler_hook(context: HookContext) -> HookResult:
    """Handle notifications from the LLM.

    Notifications carry message, title, and notification_type.
    They are informational only and cannot be blocked.
    """
    if context.event != HookEvent.NOTIFICATION:
        return HookResult()

    msg = context.event_data.get("message", "")
    title = context.event_data.get("title", "")
    ntype = context.event_data.get("notification_type", "")
    print(f"[NOTIFY] {title} ({ntype}): {msg}")

    return HookResult()


# =============================================================================
# Example 15: continue=false — Halt the Whole Run
# =============================================================================


async def killswitch_hook(context: HookContext) -> HookResult:
    """Halt all processing with `continue: false`.

    Distinct from a per-event block: `continue: false` is unconditional and ends
    the run. On UserPromptSubmit it ends the turn before the model runs; the
    `stopReason` is surfaced to the user. Here it acts as a "/stop" killswitch.
    """
    if context.event != HookEvent.USER_PROMPT_SUBMIT:
        return HookResult()

    if (context.prompt or "").strip().lower() == "/stop":
        print("[KILLSWITCH] Halting run via continue=false")
        return HookResult(
            success=True,
            modifications={
                "continue": False,
                "stopReason": "Halted by killswitch hook.",
            },
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
    # Session tracker — observe multiple events
    manager.register(
        session_tracker,
        events=[
            HookEvent.SESSION_START,
            HookEvent.USER_PROMPT_SUBMIT,
            HookEvent.POST_TOOL_USE,
            HookEvent.SESSION_END,
        ],
    )

    # Permission gate — PreToolUse only
    manager.register(permission_hook, events=[HookEvent.PRE_TOOL_USE])

    # Arg rewriting — PreToolUse only
    manager.register(arg_rewrite_hook, events=[HookEvent.PRE_TOOL_USE])

    # Journal reminder — uses Stop (per-turn), not SessionEnd (terminal)
    manager.register(
        journal_reminder,
        events=[
            HookEvent.POST_TOOL_USE,
            HookEvent.STOP,
        ],
    )

    # Response transformer — uses Stop
    # Uncomment to enable:
    # manager.register(
    #     response_transformer,
    #     events=[HookEvent.STOP],
    # )

    # Tool result blocking/redaction — PostToolUse
    manager.register(tool_result_hook, events=[HookEvent.POST_TOOL_USE])

    # Prompt gate — UserPromptSubmit
    manager.register(prompt_gate_hook, events=[HookEvent.USER_PROMPT_SUBMIT])

    # Killswitch — UserPromptSubmit (continue=false halts the whole run)
    manager.register(killswitch_hook, events=[HookEvent.USER_PROMPT_SUBMIT])

    # Pre-compact context injection
    manager.register(precompact_hook, events=[HookEvent.PRE_COMPACT])

    # Command rewriting — PreCommand only
    manager.register(command_rewrite_hook, events=[HookEvent.PRE_COMMAND])

    # Command auditing — PostCommand only
    manager.register(command_audit_hook, events=[HookEvent.POST_COMMAND])

    # Error logging — PostToolUseFailure only
    manager.register(error_log_hook, events=[HookEvent.POST_TOOL_USE_FAILURE])

    # Auto-approval — PermissionRequest only
    manager.register(auto_approve_hook, events=[HookEvent.PERMISSION_REQUEST])

    # Notification handling — Notification only
    manager.register(notification_handler_hook, events=[HookEvent.NOTIFICATION])


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
# hook_manager.register(my_hook, events=[HookEvent.STOP])

# =============================================================================
# Notes
# =============================================================================

# Hook Execution Order:
# 1. Hooks are sorted by priority (higher first)
# 2. Hooks run sequentially (not parallel)
# 3. If a hook returns should_stop=True, remaining hooks are skipped
# 4. If a hook returns block(), execution is blocked

# Hook Results quick reference:
# - HookResult()                                           Continue
# - HookResult.block(reason)                               Block (exit code 2)
# - HookResult(success=True, modifications={"continue": False,
#                                           "stopReason": "..."})
#                     Any: Halt the whole run (ends the turn on
#                     UserPromptSubmit/Stop)
# - HookResult(success=True, modifications={"systemMessage": msg})
#                     Stop: Extend turn, original response returned
# - HookResult(success=True, modifications={"systemMessage": msg,
#                                           "replaceResponse": True})
#                     Stop: Extend turn, new response replaces original
# - HookResult(success=True, modifications={"permissionDecision": "allow"})
#                     PreToolUse: Auto-allow tool (skip the prompt)
# - HookResult(success=True, modifications={"permissionDecision": "deny"})
#                     PreToolUse: Auto-deny tool
# - HookResult(success=True, modifications={"permissionDecision": "ask"})
#                     PreToolUse: Force the approval prompt
# - HookResult(success=True, modifications={"permissionDecision": "defer"})
#                     PreToolUse: No opinion (== HookResult())
# - HookResult(success=True, modifications={"updatedInput": {...}})
#                     PreToolUse: Rewrite tool args
# - HookResult(success=True, modifications={
#     "hookSpecificOutput": {"updatedToolOutput": "..."}})
#                     PostToolUse: Replace tool result
# - HookResult(success=True, modifications={"command_args": "..."})
#                     PreCommand: Rewrite command arguments
# - HookResult(success=True, modifications={
#     "hookSpecificOutput": {"additionalContext": "..."}})
#                     SessionStart/UserPromptSubmit/PreCompact:
#                     Inject additional context
# - HookResult(success=True, modifications={
#     "hookSpecificOutput": {"decision": {"behavior": "allow"}}})
#                     PermissionRequest: Auto-allow approval
# - HookResult(success=True, modifications={
#     "hookSpecificOutput": {"decision": {"behavior": "deny"}}})
#                     PermissionRequest: Auto-deny approval

# STOP vs SESSION_END:
# - Stop fires per-turn — use for journaling, summarization, block-to-continue
# - SessionEnd is terminal — fires once on chat exit (/exit, EOF, Ctrl+C)
# If migrating from SessionEnd, move per-turn hooks to Stop.

# See also:
# - .zrb/hooks.json for JSON-based command hooks
# - .zrb/hooks.yaml for YAML-based command hooks
# - custom_hook.hook.py for Python hook modules
