from enum import Enum


class HookEvent(str, Enum):
    """Hook events that are actually fired during execution."""

    SESSION_START = "SessionStart"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    # zrb-specific: bracket a UI command (any configured token, not just "/").
    # PreCommand fires before dispatch and may block it; PostCommand fires
    # after a recognized command ran. (Claude Code has no equivalent hook.)
    PRE_COMMAND = "PreCommand"
    POST_COMMAND = "PostCommand"
    PRE_TOOL_USE = "PreToolUse"
    POST_TOOL_USE = "PostToolUse"
    POST_TOOL_USE_FAILURE = "PostToolUseFailure"
    # Fired when the agent blocks waiting for the user to approve a tool call
    # (the approval cascade reached an interactive prompt). Consumers use it for
    # "needs your attention" notifications/sounds (e.g. peon-ping).
    PERMISSION_REQUEST = "PermissionRequest"
    NOTIFICATION = "Notification"
    STOP = "Stop"
    PRE_COMPACT = "PreCompact"
    SESSION_END = "SessionEnd"

    # Claude Code compatibility mapping
    @classmethod
    def from_claude_string(cls, value: str) -> "HookEvent":
        """Convert Claude Code string to HookEvent enum."""
        try:
            return cls(value)
        except ValueError:
            # Handle any case variations
            upper_value = value.upper()
            for event in cls:
                if event.value.upper() == upper_value:
                    return event
            raise ValueError(f"Unknown hook event: {value}")


class HookType(str, Enum):
    COMMAND = "command"
    PROMPT = "prompt"
    AGENT = "agent"


class MatcherOperator(str, Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    REGEX = "regex"
    GLOB = "glob"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"

    # Claude Code compatibility - regex is the standard
    @classmethod
    def from_claude_pattern(cls, pattern: str) -> "MatcherOperator":
        """Determine matcher operator from Claude Code pattern."""
        if pattern == "*" or pattern == "":
            return cls.GLOB  # Wildcard matches everything
        elif "*" in pattern or "?" in pattern or "[" in pattern:
            return cls.GLOB
        elif pattern.startswith("^") or pattern.endswith("$") or ".*" in pattern:
            return cls.REGEX
        else:
            return cls.EQUALS
