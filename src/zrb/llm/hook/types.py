from enum import Enum


class HookEvent(str, Enum):
    """All Claude Code hook events for 100% compatibility."""

    SESSION_START = "SessionStart"
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    PRE_TOOL_USE = "PreToolUse"
    PERMISSION_REQUEST = "PermissionRequest"
    POST_TOOL_USE = "PostToolUse"
    POST_TOOL_USE_FAILURE = "PostToolUseFailure"
    NOTIFICATION = "Notification"
    SUBAGENT_START = "SubagentStart"
    SUBAGENT_STOP = "SubagentStop"
    STOP = "Stop"
    TEAMMATE_IDLE = "TeammateIdle"
    TASK_COMPLETED = "TaskCompleted"
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
