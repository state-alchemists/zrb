"""Tests for auto_approve tool policy."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from zrb.llm.tool_call.tool_policy.auto_approve import auto_approve


class TestAutoApproveToolNameMismatch:
    """Test auto_approve when tool name doesn't match."""

    @pytest.mark.asyncio
    async def test_different_tool_name_passes_through(self):
        """When tool name doesn't match, delegate to next handler."""
        policy = auto_approve("MyTool")
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "OtherTool"
        next_handler = AsyncMock(return_value="next_result")

        result = await policy(ui, call, next_handler)

        assert result == "next_result"
        next_handler.assert_called_once()


class TestAutoApproveEmptyPatterns:
    """Test auto_approve with empty kwargs_patterns."""

    @pytest.mark.asyncio
    async def test_empty_patterns_approves_immediately(self):
        """Empty kwargs_patterns auto-approves any matching tool call."""
        from pydantic_ai import ToolApproved

        policy = auto_approve("MyTool", kwargs_patterns={})
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "MyTool"
        call.args = {"any": "arg"}
        next_handler = AsyncMock()

        result = await policy(ui, call, next_handler)

        assert isinstance(result, ToolApproved)
        next_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_patterns_approves_immediately(self):
        """None kwargs_patterns auto-approves any matching tool call."""
        from pydantic_ai import ToolApproved

        policy = auto_approve("MyTool", kwargs_patterns=None)
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "MyTool"
        call.args = {}
        next_handler = AsyncMock()

        result = await policy(ui, call, next_handler)

        assert isinstance(result, ToolApproved)
        next_handler.assert_not_called()


class TestAutoApproveStringArgs:
    """Test auto_approve when args are JSON strings."""

    @pytest.mark.asyncio
    async def test_json_string_args_parsed_and_approved(self):
        """JSON string args are parsed and checked against patterns."""
        from pydantic_ai import ToolApproved

        policy = auto_approve("Read", kwargs_patterns={"path": r".*\.txt"})
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "Read"
        call.args = json.dumps({"path": "file.txt"})
        next_handler = AsyncMock()

        result = await policy(ui, call, next_handler)

        assert isinstance(result, ToolApproved)

    @pytest.mark.asyncio
    async def test_invalid_json_string_passes_through(self):
        """Invalid JSON string args delegate to next handler."""
        policy = auto_approve("Read", kwargs_patterns={"path": r".*\.txt"})
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "Read"
        call.args = "not valid json"
        next_handler = AsyncMock(return_value="next_result")

        result = await policy(ui, call, next_handler)

        assert result == "next_result"
        next_handler.assert_called_once()


class TestAutoApproveNonDictArgs:
    """Test auto_approve when args are non-dict types."""

    @pytest.mark.asyncio
    async def test_non_dict_args_passes_through(self):
        """Non-dict args (e.g. list) delegate to next handler."""
        policy = auto_approve("MyTool", kwargs_patterns={"key": r".*"})
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "MyTool"
        call.args = ["list", "of", "args"]
        next_handler = AsyncMock(return_value="next_result")

        result = await policy(ui, call, next_handler)

        assert result == "next_result"
        next_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_json_non_dict_passes_through(self):
        """JSON that decodes to non-dict (e.g. list) delegates to next handler."""
        policy = auto_approve("MyTool", kwargs_patterns={"key": r".*"})
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "MyTool"
        call.args = json.dumps(["list", "of", "args"])
        next_handler = AsyncMock(return_value="next_result")

        result = await policy(ui, call, next_handler)

        assert result == "next_result"
        next_handler.assert_called_once()


class TestAutoApproveCallablePatterns:
    """Test auto_approve with callable kwargs_patterns."""

    @pytest.mark.asyncio
    async def test_callable_pattern_returns_true_approves(self):
        """Callable kwargs_patterns that returns True approves the call."""
        from pydantic_ai import ToolApproved

        policy = auto_approve("MyTool", kwargs_patterns=lambda args: True)
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "MyTool"
        call.args = {"key": "value"}
        next_handler = AsyncMock()

        result = await policy(ui, call, next_handler)

        assert isinstance(result, ToolApproved)
        next_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_callable_pattern_returns_false_passes_through(self):
        """Callable kwargs_patterns that returns False delegates to next handler."""
        policy = auto_approve("MyTool", kwargs_patterns=lambda args: False)
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "MyTool"
        call.args = {"key": "value"}
        next_handler = AsyncMock(return_value="next_result")

        result = await policy(ui, call, next_handler)

        assert result == "next_result"
        next_handler.assert_called_once()


class TestAutoApproveDictPatterns:
    """Test auto_approve with dict kwargs_patterns."""

    @pytest.mark.asyncio
    async def test_matching_pattern_approves(self):
        """Matching pattern in kwargs_patterns approves the call."""
        from pydantic_ai import ToolApproved

        policy = auto_approve("Read", kwargs_patterns={"path": r".*\.txt$"})
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "Read"
        call.args = {"path": "readme.txt"}
        next_handler = AsyncMock()

        result = await policy(ui, call, next_handler)

        assert isinstance(result, ToolApproved)

    @pytest.mark.asyncio
    async def test_non_matching_pattern_passes_through(self):
        """Non-matching pattern delegates to next handler."""
        policy = auto_approve("Read", kwargs_patterns={"path": r".*\.txt$"})
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "Read"
        call.args = {"path": "script.py"}
        next_handler = AsyncMock(return_value="next_result")

        result = await policy(ui, call, next_handler)

        assert result == "next_result"
        next_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_args_without_pattern_key_approved(self):
        """Args without keys defined in patterns are auto-approved."""
        from pydantic_ai import ToolApproved

        policy = auto_approve("Read", kwargs_patterns={"path": r".*\.txt$"})
        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "Read"
        # 'other_key' is not in kwargs_patterns, so all args pass
        call.args = {"other_key": "anything"}
        next_handler = AsyncMock()

        result = await policy(ui, call, next_handler)

        assert isinstance(result, ToolApproved)
