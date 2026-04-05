"""
Example Python Hook Module

This file demonstrates how to create standalone hook modules.
Place files with .hook.py extension in ~/.zrb/hooks/ or .zrb/hooks/

The module must define a `register(manager)` function.
"""

from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.types import HookEvent

# =============================================================================
# Example: Custom Python Hook
# =============================================================================


async def notify_on_file_write(context: HookContext) -> HookResult:
    """Notify when files are written.

    This hook fires after Write or Edit tool usage and logs the action.
    """
    if context.event != HookEvent.POST_TOOL_USE:
        return HookResult()

    # Check if tool is file-related
    file_tools = {"Write", "Edit", "WriteMany"}
    if context.tool_name not in file_tools:
        return HookResult()

    # Get file path from tool input
    tool_input = context.tool_input or {}
    file_path = tool_input.get("path", "unknown")

    # Log the file operation
    print(f"[FILE WRITE] {context.tool_name}: {file_path}")

    # Could also:
    # - Write to a log file
    # - Send to a monitoring service
    # - Update a database
    # - Trigger other actions

    return HookResult()


# =============================================================================
# Example: Rate Limiting Hook
# =============================================================================


class RateLimitHook:
    """Limit tool usage rate.

    Demonstrates stateful hooks that track usage over time.
    """

    def __init__(self, max_per_minute: int = 30):
        self.max_per_minute = max_per_minute
        self.calls: list[float] = []

    def _cleanup_old_calls(self):
        """Remove calls older than 1 minute."""
        import time

        cutoff = time.time() - 60
        self.calls = [t for t in self.calls if t > cutoff]

    async def __call__(self, context: HookContext) -> HookResult:
        import time

        if context.event != HookEvent.PRE_TOOL_USE:
            return HookResult()

        # Check rate
        self._cleanup_old_calls()

        if len(self.calls) >= self.max_per_minute:
            # Block the request
            return HookResult.block(
                reason=f"Rate limit exceeded: {self.max_per_minute} calls per minute",
                additional_context="Please wait before making more tool calls.",
            )

        # Track the call
        self.calls.append(time.time())

        # Allow the request
        return HookResult()


# =============================================================================
# Example: Audit Logging Hook
# =============================================================================


async def audit_log_hook(context: HookContext) -> HookResult:
    """Log all significant events for audit purposes.

    Demonstrates extracting context information from various event types.
    """
    import json
    import os
    from datetime import datetime

    # Create audit entry
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": context.event.value,
        "session_id": context.session_id,
    }

    # Add event-specific data
    if context.tool_name:
        entry["tool"] = context.tool_name

    if context.tool_input:
        # Sanitize sensitive data
        safe_input = dict(context.tool_input)
        if "content" in safe_input and len(str(safe_input.get("content", ""))) > 100:
            safe_input["content"] = str(safe_input["content"])[:100] + "..."
        entry["tool_input"] = safe_input

    if context.prompt:
        entry["prompt_length"] = len(context.prompt)

    if context.error:
        entry["error"] = context.error

    # Write to audit log
    log_dir = os.path.expanduser("~/.zrb/logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "audit.log")

    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return HookResult()


# =============================================================================
# Register function (required)
# =============================================================================


def register(manager):
    """Register hooks with the manager.

    This function is called automatically when the hook module is loaded.
    """
    # Create rate limiter instance
    rate_limiter = RateLimitHook(max_per_minute=60)

    # Register hooks
    manager.register(notify_on_file_write, events=[HookEvent.POST_TOOL_USE])
    manager.register(rate_limiter, events=[HookEvent.PRE_TOOL_USE])
    manager.register(audit_log_hook, events=None)  # Global - all events


# =============================================================================
# Alternative register_hooks function
# =============================================================================


def register_hooks(manager):
    """Alternative registration function (also supported)."""
    return register(manager)
