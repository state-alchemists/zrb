from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

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

    def to_claude_json(self) -> dict[str, Any]:
        """Convert to Claude Code compatible JSON format."""
        base = {
            "session_id": self.session_id,
            "transcript_path": self.transcript_path,
            "cwd": self.cwd,
            "permission_mode": self.permission_mode,
            "hook_event_name": self.hook_event_name or self.event.value,
        }

        # Add event-specific fields
        if self.prompt is not None:
            base["prompt"] = self.prompt

        if self.tool_name is not None:
            base["tool_name"] = self.tool_name

        if self.tool_input is not None:
            base["tool_input"] = self.tool_input

        if self.tool_response is not None:
            base["tool_response"] = self.tool_response

        if self.tool_use_id is not None:
            base["tool_use_id"] = self.tool_use_id

        if self.error is not None:
            base["error"] = self.error

        if self.is_interrupt is not None:
            base["is_interrupt"] = self.is_interrupt

        if self.message is not None:
            base["message"] = self.message

        if self.title is not None:
            base["title"] = self.title

        if self.notification_type is not None:
            base["notification_type"] = self.notification_type

        if self.agent_id is not None:
            base["agent_id"] = self.agent_id

        if self.agent_type is not None:
            base["agent_type"] = self.agent_type

        if self.agent_transcript_path is not None:
            base["agent_transcript_path"] = self.agent_transcript_path

        if self.stop_hook_active is not None:
            base["stop_hook_active"] = self.stop_hook_active

        if self.teammate_name is not None:
            base["teammate_name"] = self.teammate_name

        if self.team_name is not None:
            base["team_name"] = self.team_name

        if self.task_id is not None:
            base["task_id"] = self.task_id

        if self.task_subject is not None:
            base["task_subject"] = self.task_subject

        if self.task_description is not None:
            base["task_description"] = self.task_description

        if self.trigger is not None:
            base["trigger"] = self.trigger

        if self.custom_instructions is not None:
            base["custom_instructions"] = self.custom_instructions

        if self.reason is not None:
            base["reason"] = self.reason

        if self.source is not None:
            base["source"] = self.source

        if self.model is not None:
            base["model"] = self.model

        if self.permission_suggestions is not None:
            base["permission_suggestions"] = self.permission_suggestions

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

    @classmethod
    def allow(
        cls,
        permission_decision: str = "allow",
        reason: str | None = None,
        updated_input: dict[str, Any] | None = None,
        additional_context: str | None = None,
    ) -> "HookResult":
        """Create an allow result for PreToolUse hooks."""
        modifications = {"permissionDecision": permission_decision, "exit_code": 0}
        if reason:
            modifications["permissionDecisionReason"] = reason
        if updated_input:
            modifications["updatedInput"] = updated_input
        if additional_context:
            modifications["additionalContext"] = additional_context
        return cls(success=True, modifications=modifications)

    @classmethod
    def ask(cls, reason: str, additional_context: str | None = None) -> "HookResult":
        """Create an ask result for PreToolUse hooks."""
        modifications = {
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
            "exit_code": 0,
        }
        if additional_context:
            modifications["additionalContext"] = additional_context
        return cls(success=True, modifications=modifications)

    @classmethod
    def deny(cls, reason: str, additional_context: str | None = None) -> "HookResult":
        """Create a deny result for PreToolUse hooks."""
        modifications = {
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "exit_code": 0,
        }
        if additional_context:
            modifications["additionalContext"] = additional_context
        return cls(success=True, modifications=modifications)

    @classmethod
    def with_system_message(cls, message: str) -> "HookResult":
        """Create a result with a system message."""
        return cls(success=True, modifications={"systemMessage": message})

    @classmethod
    def with_additional_context(cls, context: str) -> "HookResult":
        """Create a result with additional context."""
        return cls(success=True, modifications={"additionalContext": context})

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
