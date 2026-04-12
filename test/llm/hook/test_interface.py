"""Tests for HookContext and HookResult from interface.py."""

import pytest

from zrb.llm.hook.interface import HookContext, HookResult
from zrb.llm.hook.types import HookEvent


class TestHookContext:
    """Test HookContext dataclass."""

    def test_basic_creation(self):
        """Test creating a basic HookContext."""
        ctx = HookContext(event=HookEvent.SESSION_START, event_data={"key": "value"})
        assert ctx.event == HookEvent.SESSION_START
        assert ctx.event_data == {"key": "value"}
        assert ctx.session_id is None
        assert ctx.metadata == {}

    def test_creation_with_all_fields(self):
        """Test creating HookContext with all fields."""
        ctx = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            event_data={"input": "test"},
            session_id="session-123",
            metadata={"user": "admin"},
            transcript_path="/path/to/transcript",
            cwd="/working/dir",
            permission_mode="ask",
            hook_event_name="PreToolUse",
            prompt="test prompt",
            tool_name="Read",
            tool_input={"path": "/file.txt"},
            tool_response={"content": "data"},
            tool_use_id="tool-123",
            error="test error",
            is_interrupt=True,
            message="test message",
            title="test title",
            notification_type="info",
            agent_id="agent-123",
            agent_type="executor",
            agent_transcript_path="/agent/transcript",
            stop_hook_active=True,
            teammate_name="helper",
            team_name="team-a",
            task_id="task-123",
            task_subject="Do something",
            task_description="Description here",
            trigger="manual",
            custom_instructions="Be careful",
            reason="User requested",
            source="user",
            model="claude-3",
            permission_suggestions=[{"role": "admin"}],
        )
        assert ctx.event == HookEvent.PRE_TOOL_USE
        assert ctx.session_id == "session-123"
        assert ctx.tool_name == "Read"
        assert ctx.tool_input == {"path": "/file.txt"}
        assert ctx.permission_suggestions == [{"role": "admin"}]

    def test_to_claude_json_basic(self):
        """Test to_claude_json with minimal fields."""
        ctx = HookContext(event=HookEvent.SESSION_START, event_data={})
        result = ctx.to_claude_json()
        assert "session_id" in result
        assert "transcript_path" in result
        assert "cwd" in result
        assert "permission_mode" in result
        assert "hook_event_name" in result
        assert result["hook_event_name"] == "SessionStart"

    def test_to_claude_json_with_hook_event_name(self):
        """Test to_claude_json uses hook_event_name if set."""
        ctx = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            event_data={},
            hook_event_name="CustomHookName",
        )
        result = ctx.to_claude_json()
        assert result["hook_event_name"] == "CustomHookName"

    def test_to_claude_json_with_tool_fields(self):
        """Test to_claude_json includes tool-related fields."""
        ctx = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            event_data={},
            tool_name="Bash",
            tool_input={"command": "ls"},
            tool_use_id="tool-123",
        )
        result = ctx.to_claude_json()
        assert result["tool_name"] == "Bash"
        assert result["tool_input"] == {"command": "ls"}
        assert result["tool_use_id"] == "tool-123"

    def test_to_claude_json_with_prompt(self):
        """Test to_claude_json includes prompt field."""
        ctx = HookContext(
            event=HookEvent.USER_PROMPT_SUBMIT, event_data={}, prompt="Hello world"
        )
        result = ctx.to_claude_json()
        assert result["prompt"] == "Hello world"

    def test_to_claude_json_with_error(self):
        """Test to_claude_json includes error field."""
        ctx = HookContext(
            event=HookEvent.POST_TOOL_USE_FAILURE,
            event_data={},
            error="Something failed",
        )
        result = ctx.to_claude_json()
        assert result["error"] == "Something failed"

    def test_to_claude_json_with_notification_fields(self):
        """Test to_claude_json includes notification fields."""
        ctx = HookContext(
            event=HookEvent.NOTIFICATION,
            event_data={},
            message="Alert!",
            title="Warning",
            notification_type="warning",
        )
        result = ctx.to_claude_json()
        assert result["message"] == "Alert!"
        assert result["title"] == "Warning"
        assert result["notification_type"] == "warning"

    def test_to_claude_json_with_agent_fields(self):
        """Test to_claude_json includes agent fields."""
        ctx = HookContext(
            event=HookEvent.NOTIFICATION,
            event_data={},
            agent_id="agent-123",
            agent_type="code-reviewer",
            agent_transcript_path="/transcripts/agent-123",
        )
        result = ctx.to_claude_json()
        assert result["agent_id"] == "agent-123"
        assert result["agent_type"] == "code-reviewer"
        assert result["agent_transcript_path"] == "/transcripts/agent-123"

    def test_to_claude_json_with_task_fields(self):
        """Test to_claude_json includes task fields."""
        ctx = HookContext(
            event=HookEvent.SESSION_END,
            event_data={},
            task_id="task-123",
            task_subject="Build feature",
            task_description="Implement X",
        )
        result = ctx.to_claude_json()
        assert result["task_id"] == "task-123"
        assert result["task_subject"] == "Build feature"
        assert result["task_description"] == "Implement X"

    def test_to_claude_json_with_source(self):
        """Test to_claude_json includes source field."""
        ctx = HookContext(
            event=HookEvent.SESSION_START, event_data={}, source="cli", model="claude-3"
        )
        result = ctx.to_claude_json()
        assert result["source"] == "cli"
        assert result["model"] == "claude-3"

    def test_to_claude_json_omits_none_values(self):
        """Test that to_claude_json omits None values."""
        ctx = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            event_data={},
            tool_name="Read",
            prompt=None,  # Should not be included
            tool_input=None,  # Should not be included
        )
        result = ctx.to_claude_json()
        assert "tool_name" in result
        assert "prompt" not in result
        assert "tool_input" not in result

    def test_to_claude_json_with_tool_response_and_interrupt(self):
        """Test to_claude_json includes tool_response and is_interrupt."""
        ctx = HookContext(
            event=HookEvent.POST_TOOL_USE,
            event_data={},
            tool_response={"result": "ok"},
            is_interrupt=False,
        )
        result = ctx.to_claude_json()
        assert result["tool_response"] == {"result": "ok"}
        assert result["is_interrupt"] is False

    def test_to_claude_json_with_stop_hook_and_team_fields(self):
        """Test to_claude_json includes stop_hook_active, teammate_name, team_name."""
        ctx = HookContext(
            event=HookEvent.STOP,
            event_data={},
            stop_hook_active=True,
            teammate_name="helper-bot",
            team_name="core-team",
        )
        result = ctx.to_claude_json()
        assert result["stop_hook_active"] is True
        assert result["teammate_name"] == "helper-bot"
        assert result["team_name"] == "core-team"

    def test_to_claude_json_with_trigger_and_instructions_and_reason(self):
        """Test to_claude_json includes trigger, custom_instructions, reason."""
        ctx = HookContext(
            event=HookEvent.PRE_COMPACT,
            event_data={},
            trigger="auto",
            custom_instructions="Be concise",
            reason="context limit reached",
        )
        result = ctx.to_claude_json()
        assert result["trigger"] == "auto"
        assert result["custom_instructions"] == "Be concise"
        assert result["reason"] == "context limit reached"

    def test_to_claude_json_with_permission_suggestions(self):
        """Test to_claude_json includes permission_suggestions."""
        ctx = HookContext(
            event=HookEvent.PRE_TOOL_USE,
            event_data={},
            permission_suggestions=[{"tool": "Bash", "action": "allow"}],
        )
        result = ctx.to_claude_json()
        assert result["permission_suggestions"] == [{"tool": "Bash", "action": "allow"}]


class TestHookResultBlock:
    """Test HookResult.block() class method."""

    def test_block_basic(self):
        """Test block() with reason only."""
        result = HookResult.block("Access denied")
        assert result.success is False
        assert result.should_stop is True
        assert result.modifications["decision"] == "block"
        assert result.modifications["reason"] == "Access denied"
        assert result.modifications["exit_code"] == 2

    def test_block_with_additional_context(self):
        """Test block() with additional context."""
        result = HookResult.block("Forbidden", "See policy doc")
        assert result.modifications["additionalContext"] == "See policy doc"


class TestHookResultAllow:
    """Test HookResult.allow() class method."""

    def test_allow_basic(self):
        """Test allow() with default arguments."""
        result = HookResult.allow()
        assert result.success is True
        assert result.modifications["permissionDecision"] == "allow"
        assert result.modifications["exit_code"] == 0

    def test_allow_with_reason(self):
        """Test allow() with reason."""
        result = HookResult.allow(reason="Trusted source")
        assert result.modifications["permissionDecision"] == "allow"
        assert result.modifications["permissionDecisionReason"] == "Trusted source"

    def test_allow_with_updated_input(self):
        """Test allow() with updated input."""
        result = HookResult.allow(updated_input={"path": "/new/path"})
        assert result.modifications["updatedInput"] == {"path": "/new/path"}

    def test_allow_with_all_options(self):
        """Test allow() with all options."""
        result = HookResult.allow(
            permission_decision="allow",
            reason="Verified",
            updated_input={"arg": "value"},
            additional_context="Context info",
        )
        assert result.modifications["permissionDecision"] == "allow"
        assert result.modifications["permissionDecisionReason"] == "Verified"
        assert result.modifications["updatedInput"] == {"arg": "value"}
        assert result.modifications["additionalContext"] == "Context info"


class TestHookResultAsk:
    """Test HookResult.ask() class method."""

    def test_ask_basic(self):
        """Test ask() with reason only."""
        result = HookResult.ask("Please confirm")
        assert result.success is True
        assert result.modifications["permissionDecision"] == "ask"
        assert result.modifications["permissionDecisionReason"] == "Please confirm"
        assert result.modifications["exit_code"] == 0

    def test_ask_with_additional_context(self):
        """Test ask() with additional context."""
        result = HookResult.ask("Confirm?", "Need more info")
        assert result.modifications["additionalContext"] == "Need more info"


class TestHookResultDeny:
    """Test HookResult.deny() class method."""

    def test_deny_basic(self):
        """Test deny() with reason only."""
        result = HookResult.deny("Not allowed")
        assert result.success is True
        assert result.modifications["permissionDecision"] == "deny"
        assert result.modifications["permissionDecisionReason"] == "Not allowed"
        assert result.modifications["exit_code"] == 0

    def test_deny_with_additional_context(self):
        """Test deny() with additional context."""
        result = HookResult.deny("Forbidden", "Policy violation")
        assert result.modifications["additionalContext"] == "Policy violation"


class TestHookResultWithMethods:
    """Test HookResult with_*() class methods."""

    def test_with_system_message(self):
        """Test with_system_message()."""
        result = HookResult.with_system_message("System Alert!")
        assert result.success is True
        assert result.modifications["systemMessage"] == "System Alert!"

    def test_with_additional_context(self):
        """Test with_additional_context()."""
        result = HookResult.with_additional_context("Extra context here")
        assert result.success is True
        assert result.modifications["additionalContext"] == "Extra context here"


class TestHookResultToClaudeJson:
    """Test HookResult.to_claude_json() method."""

    def test_to_claude_json_basic(self):
        """Test basic to_claude_json conversion."""
        result = HookResult(success=True, output="test output")
        json_result = result.to_claude_json()
        assert json_result["success"] is True
        assert json_result["output"] == "test output"
        assert json_result["exit_code"] == 0

    def test_to_claude_json_with_data(self):
        """Test to_claude_json with data."""
        result = HookResult(success=True, data={"key": "value"})
        json_result = result.to_claude_json()
        assert json_result["data"] == {"key": "value"}

    def test_to_claude_json_with_modifications(self):
        """Test to_claude_json merges modifications."""
        result = HookResult(
            success=True, modifications={"custom_field": "custom_value"}
        )
        json_result = result.to_claude_json()
        assert json_result["custom_field"] == "custom_value"

    def test_to_claude_json_blocking_result(self):
        """Test to_claude_json for blocking result."""
        result = HookResult(success=False, should_stop=True, output="Blocked!")
        json_result = result.to_claude_json()
        assert json_result["decision"] == "block"
        assert json_result["reason"] == "Blocked!"
        assert json_result["exit_code"] == 2
        assert json_result["success"] is False

    def test_to_claude_json_blocking_with_modifications(self):
        """Test to_claude_json for blocking result with modifications."""
        result = HookResult(
            success=False,
            should_stop=True,
            modifications={"reason": "Custom reason", "exit_code": 2},
        )
        json_result = result.to_claude_json()
        assert json_result["reason"] == "Custom reason"
        assert json_result["exit_code"] == 2

    def test_to_claude_json_permission_decision_to_hook_specific_output(self):
        """Test that permissionDecision is moved to hookSpecificOutput."""
        result = HookResult(
            success=True,
            modifications={
                "permissionDecision": "allow",
                "permissionDecisionReason": "Trusted",
                "updatedInput": {"arg": "val"},
            },
        )
        json_result = result.to_claude_json()
        assert "permissionDecision" not in json_result
        assert json_result["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert (
            json_result["hookSpecificOutput"]["permissionDecisionReason"] == "Trusted"
        )
        assert json_result["hookSpecificOutput"]["updatedInput"] == {"arg": "val"}

    def test_to_claude_json_exits_code_0_by_default(self):
        """Test that exit_code defaults to 0 for successful results."""
        result = HookResult(success=True)
        json_result = result.to_claude_json()
        assert json_result["exit_code"] == 0

    def test_to_claude_json_no_output_when_none(self):
        """Test that output is not included when None."""
        result = HookResult(success=True, output=None)
        json_result = result.to_claude_json()
        assert "output" not in json_result or json_result.get("output") is None

    def test_to_claude_json_non_dict_hook_specific_output_is_preserved(self):
        """Test that a non-dict hookSpecificOutput is left as-is (defensive pass)."""
        result = HookResult(
            success=True,
            modifications={"hookSpecificOutput": "already-serialized-string"},
        )
        json_result = result.to_claude_json()
        # The pass branch leaves the value unchanged; permissionDecision check is skipped
        assert json_result["hookSpecificOutput"] == "already-serialized-string"


class TestHookResultIntegration:
    """Integration tests for HookResult."""

    def test_block_to_claude_json_integration(self):
        """Test block() result converted to Claude JSON."""
        result = HookResult.block("Security violation", "See policy")
        json_result = result.to_claude_json()
        assert json_result["decision"] == "block"
        assert json_result["reason"] == "Security violation"
        assert json_result["additionalContext"] == "See policy"
        assert json_result["exit_code"] == 2
        assert json_result["success"] is False

    def test_allow_to_claude_json_integration(self):
        """Test allow() result converted to Claude JSON."""
        result = HookResult.allow(
            reason="Trusted", updated_input={"path": "/safe/path"}
        )
        json_result = result.to_claude_json()
        assert json_result["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert (
            json_result["hookSpecificOutput"]["permissionDecisionReason"] == "Trusted"
        )
        assert json_result["hookSpecificOutput"]["updatedInput"] == {
            "path": "/safe/path"
        }
        assert json_result["success"] is True
        assert json_result["exit_code"] == 0
