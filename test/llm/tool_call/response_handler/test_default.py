"""Tests for default.py response handler."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDefaultResponseHandler:
    """Test default_response_handler function."""

    @pytest.mark.asyncio
    async def test_response_yes(self):
        """Test 'yes' response approves execution."""
        from zrb.llm.tool_call.response_handler.default import default_response_handler
        from pydantic_ai import ToolApproved

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        result = await default_response_handler(ui, call, "yes", AsyncMock())

        assert isinstance(result, ToolApproved)

    @pytest.mark.asyncio
    async def test_response_y(self):
        """Test 'y' response approves execution."""
        from zrb.llm.tool_call.response_handler.default import default_response_handler
        from pydantic_ai import ToolApproved

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        result = await default_response_handler(ui, call, "y", AsyncMock())

        assert isinstance(result, ToolApproved)

    @pytest.mark.asyncio
    async def test_response_okay(self):
        """Test 'okay' response approves execution."""
        from zrb.llm.tool_call.response_handler.default import default_response_handler
        from pydantic_ai import ToolApproved

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        result = await default_response_handler(ui, call, "okay", AsyncMock())

        assert isinstance(result, ToolApproved)

    @pytest.mark.asyncio
    async def test_response_empty_string(self):
        """Test empty string response approves execution."""
        from zrb.llm.tool_call.response_handler.default import default_response_handler
        from pydantic_ai import ToolApproved

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        result = await default_response_handler(ui, call, "", AsyncMock())

        assert isinstance(result, ToolApproved)

    @pytest.mark.asyncio
    async def test_response_no(self):
        """Test 'no' response denies execution."""
        from zrb.llm.tool_call.response_handler.default import default_response_handler
        from pydantic_ai import ToolDenied

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        result = await default_response_handler(ui, call, "no", AsyncMock())

        assert isinstance(result, ToolDenied)

    @pytest.mark.asyncio
    async def test_response_n(self):
        """Test 'n' response denies execution."""
        from zrb.llm.tool_call.response_handler.default import default_response_handler
        from pydantic_ai import ToolDenied

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        result = await default_response_handler(ui, call, "n", AsyncMock())

        assert isinstance(result, ToolDenied)

    @pytest.mark.asyncio
    async def test_response_custom_message(self):
        """Test custom message denies execution."""
        from zrb.llm.tool_call.response_handler.default import default_response_handler
        from pydantic_ai import ToolDenied

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        result = await default_response_handler(ui, call, "I don't want to", AsyncMock())

        assert isinstance(result, ToolDenied)
        assert "I don't want to" in result.message

    @pytest.mark.asyncio
    async def test_response_case_insensitive(self):
        """Test case insensitive responses."""
        from zrb.llm.tool_call.response_handler.default import default_response_handler
        from pydantic_ai import ToolApproved

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        result = await default_response_handler(ui, call, "YES", AsyncMock())
        assert isinstance(result, ToolApproved)

        result = await default_response_handler(ui, call, "  Yes  ", AsyncMock())
        assert isinstance(result, ToolApproved)


class TestWaitEditContent:
    """Test _wait_edit_content function."""

    @pytest.mark.asyncio
    async def test_wait_edit_content_creates_tempfile(self):
        """Test that _wait_edit_content creates tempfile and calls editor."""
        from zrb.llm.tool_call.response_handler.default import _wait_edit_content

        ui = MagicMock()
        ui.run_interactive_command = AsyncMock()

        content = "test content"

        result = await _wait_edit_content(
            ui=ui,
            text_editor="cat",  # Use cat as safe editor
            content=content,
            extension=".txt",
        )

        # Verify the tempfile was created and the content was read
        assert result == content