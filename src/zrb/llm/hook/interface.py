from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, ClassVar

from zrb.llm.hook.types import HookEvent


@dataclass
class HookContext:
    """Claude Code compatible hook context."""

    event: HookEvent
    event_data: Any
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Claude Code standard fields
    transcript_path: str | None = None
    cwd: str | None = None
    permission_mode: str = "default"
    hook_event_name: str | None = None  # For compatibility with Claude Code JSON

    # Event-specific fields (populated based on event type)
    prompt: str | None = None  # UserPromptSubmit
    command_name: str | None = None  # Pre/PostCommand — e.g. "/save" or ">"
    command_args: str | None = None  # Pre/PostCommand — text after the token
    command_handled: bool | None = None  # PostCommand — a handler consumed it
    tool_name: str | None = None  # PreToolUse, PostToolUse, etc.
    tool_input: dict[str, Any] | None = None
    tool_response: dict[str, Any] | None = None
    tool_use_id: str | None = None
    error: str | None = None  # PostToolUseFailure
    is_interrupt: bool | None = None
    message: str | None = None  # Notification
    title: str | None = None
    notification_type: str | None = None
    agent_id: str | None = None  # SubagentStart/Stop
    agent_type: str | None = None
    agent_transcript_path: str | None = None
    stop_hook_active: bool | None = None  # Stop
    teammate_name: str | None = None  # TeammateIdle
    team_name: str | None = None
    task_id: str | None = None  # TaskCompleted
    task_subject: str | None = None
    task_description: str | None = None
    trigger: str | None = None  # PreCompact
    custom_instructions: str | None = None
    reason: str | None = None  # SessionEnd
    source: str | None = None  # SessionStart
    model: str | None = None
    permission_suggestions: list[dict[str, Any]] | None = None  # PermissionRequest

    # Fields to include in JSON output when non-None
    _JSON_FIELDS: "ClassVar[list[str]]" = [
        "prompt",
        "command_name",
        "command_args",
        "command_handled",
        "tool_name",
        "tool_input",
        "tool_response",
        "tool_use_id",
        "error",
        "is_interrupt",
        "message",
        "title",
        "notification_type",
        "agent_id",
        "agent_type",
        "agent_transcript_path",
        "stop_hook_active",
        "teammate_name",
        "team_name",
        "task_id",
        "task_subject",
        "task_description",
        "trigger",
        "custom_instructions",
        "reason",
        "source",
        "model",
        "permission_suggestions",
    ]

    def to_claude_json(self) -> dict[str, Any]:
        """Convert to Claude Code compatible JSON format."""
        base = {
            "session_id": self.session_id,
            "transcript_path": self.transcript_path,
            "cwd": self.cwd,
            "permission_mode": self.permission_mode,
            "hook_event_name": self.hook_event_name or self.event.value,
        }
        for json_field in self._JSON_FIELDS:
            value = getattr(self, json_field, None)
            if value is not None:
                base[json_field] = value
        return base


@dataclass
class HookResult:
    """Claude Code compatible hook result."""

    success: bool = True
    output: str | None = None
    data: dict[str, Any] | None = None
    modifications: dict[str, Any] = field(default_factory=dict)
    should_stop: bool = False

    # Claude Code compatibility helpers
    @classmethod
    def block(cls, reason: str, additional_context: str | None = None) -> "HookResult":
        """Create a blocking result (exit code 2 in Claude Code)."""
        modifications = {"decision": "block", "reason": reason, "exit_code": 2}
        if additional_context:
            modifications["additionalContext"] = additional_context
        return cls(success=False, should_stop=True, modifications=modifications)

    def to_claude_json(self) -> dict[str, Any]:
        """Convert to Claude Code compatible JSON output."""
        result = {}

        # Merge modifications first
        if self.modifications:
            result.update(self.modifications)

        # Handle hookSpecificOutput - should be a dictionary
        if "hookSpecificOutput" in result and not isinstance(
            result["hookSpecificOutput"], dict
        ):
            # If it's not a dict, we might want to wrap it or leave it if it's already correct?
            # Claude expects object with fields like permissionDecision
            pass

        # Handle specific fields that should be in hookSpecificOutput for PreToolUse
        # If permissionDecision is present, it's likely a PreToolUse result that belongs in hookSpecificOutput
        if "permissionDecision" in result:
            if "hookSpecificOutput" not in result:
                result["hookSpecificOutput"] = {}
            result["hookSpecificOutput"]["permissionDecision"] = result.pop(
                "permissionDecision"
            )
            if "permissionDecisionReason" in result:
                result["hookSpecificOutput"]["permissionDecisionReason"] = result.pop(
                    "permissionDecisionReason"
                )
            if "updatedInput" in result:
                result["hookSpecificOutput"]["updatedInput"] = result.pop(
                    "updatedInput"
                )

        # Add basic fields
        result["success"] = self.success
        if self.output:
            result["output"] = self.output
        if self.data:
            result["data"] = self.data

        # Handle blocking case - ensure decision and reason are set
        if not self.success and self.should_stop:
            result["decision"] = "block"
            # Use reason from modifications if available, otherwise use output
            if "reason" not in result:
                result["reason"] = self.output or "Blocked by hook"
            if "exit_code" not in result:
                result["exit_code"] = 2
        elif "exit_code" not in result:
            result["exit_code"] = 0

        return result


HookCallable = Callable[[HookContext], Awaitable[HookResult]]
