"""Tests for default.py response handler."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDefaultResponseHandler:
    """Test default_response_handler function."""

    @pytest.mark.asyncio
    async def test_response_yes(self):
        """Test 'yes' response approves execution."""
        from pydantic_ai import ToolApproved

        from zrb.llm.tool_call.response_handler.default import default_response_handler

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        result = await default_response_handler(ui, call, "yes", AsyncMock())

        assert isinstance(result, ToolApproved)

    @pytest.mark.asyncio
    async def test_response_y(self):
        """Test 'y' response approves execution."""
        from pydantic_ai import ToolApproved

        from zrb.llm.tool_call.response_handler.default import default_response_handler

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        result = await default_response_handler(ui, call, "y", AsyncMock())

        assert isinstance(result, ToolApproved)

    @pytest.mark.asyncio
    async def test_response_okay(self):
        """Test 'okay' response approves execution."""
        from pydantic_ai import ToolApproved

        from zrb.llm.tool_call.response_handler.default import default_response_handler

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        result = await default_response_handler(ui, call, "okay", AsyncMock())

        assert isinstance(result, ToolApproved)

    @pytest.mark.asyncio
    async def test_response_empty_string(self):
        """Test empty string response approves execution."""
        from pydantic_ai import ToolApproved

        from zrb.llm.tool_call.response_handler.default import default_response_handler

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        result = await default_response_handler(ui, call, "", AsyncMock())

        assert isinstance(result, ToolApproved)

    @pytest.mark.asyncio
    async def test_response_no(self):
        """Test 'no' response denies execution."""
        from pydantic_ai import ToolDenied

        from zrb.llm.tool_call.response_handler.default import default_response_handler

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        result = await default_response_handler(ui, call, "no", AsyncMock())

        assert isinstance(result, ToolDenied)

    @pytest.mark.asyncio
    async def test_response_n(self):
        """Test 'n' response denies execution."""
        from pydantic_ai import ToolDenied

        from zrb.llm.tool_call.response_handler.default import default_response_handler

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        result = await default_response_handler(ui, call, "n", AsyncMock())

        assert isinstance(result, ToolDenied)

    @pytest.mark.asyncio
    async def test_response_custom_message(self):
        """Test custom message denies execution."""
        from pydantic_ai import ToolDenied

        from zrb.llm.tool_call.response_handler.default import default_response_handler

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        result = await default_response_handler(
            ui, call, "I don't want to", AsyncMock()
        )

        assert isinstance(result, ToolDenied)
        assert "I don't want to" in result.message

    @pytest.mark.asyncio
    async def test_response_case_insensitive(self):
        """Test case insensitive responses."""
        from pydantic_ai import ToolApproved

        from zrb.llm.tool_call.response_handler.default import default_response_handler

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        result = await default_response_handler(ui, call, "YES", AsyncMock())
        assert isinstance(result, ToolApproved)

        result = await default_response_handler(ui, call, "  Yes  ", AsyncMock())
        assert isinstance(result, ToolApproved)


class TestDefaultResponseHandlerEdit:
    """Test default_response_handler edit functionality."""

    @pytest.mark.asyncio
    async def test_response_edit_with_modified_args(self):
        """Test 'edit' response with modified arguments approves with override."""
        from pydantic_ai import ToolApproved

        from zrb.llm.tool_call.response_handler.default import default_response_handler

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "original"}

        async def mock_edit_content_via_editor(ui, args, text_editor=None):
            return {"command": "modified"}

        with patch(
            "zrb.llm.tool_call.edit_util.edit_content_via_editor",
            mock_edit_content_via_editor,
        ):
            result = await default_response_handler(ui, call, "edit", AsyncMock())

        assert isinstance(result, ToolApproved)
        assert result.override_args == {"command": "modified"}

    @pytest.mark.asyncio
    async def test_response_edit_with_str_args(self):
        """Test 'edit' response with string args parses JSON."""
        from pydantic_ai import ToolApproved

        from zrb.llm.tool_call.response_handler.default import default_response_handler

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = '{"command": "test"}'  # String args

        async def mock_edit_content_via_editor(ui, args, text_editor=None):
            return {"command": "edited"}

        with patch(
            "zrb.llm.tool_call.edit_util.edit_content_via_editor",
            mock_edit_content_via_editor,
        ):
            result = await default_response_handler(ui, call, "e", AsyncMock())

        assert isinstance(result, ToolApproved)

    @pytest.mark.asyncio
    async def test_response_edit_with_invalid_json_string_args(self):
        """Test 'edit' response with invalid JSON string uses empty dict."""
        from pydantic_ai import ToolApproved

        from zrb.llm.tool_call.response_handler.default import default_response_handler

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = "not valid json"  # Invalid JSON string

        async def mock_edit_content_via_editor(ui, args, text_editor=None):
            assert args == {}  # Should fallback to empty dict
            return {"command": "new"}

        with patch(
            "zrb.llm.tool_call.edit_util.edit_content_via_editor",
            mock_edit_content_via_editor,
        ):
            result = await default_response_handler(ui, call, "edit", AsyncMock())

        assert isinstance(result, ToolApproved)

    @pytest.mark.asyncio
    async def test_response_edit_with_non_dict_args(self):
        """Test 'edit' response with non-dict args converts to empty dict."""
        from pydantic_ai import ToolApproved

        from zrb.llm.tool_call.response_handler.default import default_response_handler

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = 123  # Non-dict, non-string args

        async def mock_edit_content_via_editor(ui, args, text_editor=None):
            assert args == {}  # Should fallback to empty dict
            return {"command": "new"}

        with patch(
            "zrb.llm.tool_call.edit_util.edit_content_via_editor",
            mock_edit_content_via_editor,
        ):
            result = await default_response_handler(ui, call, "edit", AsyncMock())

        assert isinstance(result, ToolApproved)

    @pytest.mark.asyncio
    async def test_response_edit_returns_none_on_invalid_format(self):
        """Test 'edit' response returns None when edit_content_via_editor returns None."""
        from zrb.llm.tool_call.response_handler.default import default_response_handler

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        async def mock_edit_content_via_editor(ui, args, text_editor=None):
            return None  # Invalid format

        with patch(
            "zrb.llm.tool_call.edit_util.edit_content_via_editor",
            mock_edit_content_via_editor,
        ):
            result = await default_response_handler(ui, call, "edit", AsyncMock())

        assert result is None

    @pytest.mark.asyncio
    async def test_response_edit_returns_none_on_no_changes(self):
        """Test 'edit' response returns None when no changes made."""
        from zrb.llm.tool_call.response_handler.default import default_response_handler

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        async def mock_edit_content_via_editor(ui, args, text_editor=None):
            return args  # Same as input, no changes

        with patch(
            "zrb.llm.tool_call.edit_util.edit_content_via_editor",
            mock_edit_content_via_editor,
        ):
            result = await default_response_handler(ui, call, "edit", AsyncMock())

        assert result is None

    @pytest.mark.asyncio
    async def test_response_edit_handles_exception(self):
        """Test 'edit' response handles exceptions gracefully."""
        from zrb.llm.tool_call.response_handler.default import default_response_handler

        ui = MagicMock()
        ui.append_to_output = MagicMock()

        call = MagicMock()
        call.args = {"command": "test"}

        async def mock_edit_content_via_editor(ui, args, text_editor=None):
            raise ValueError("Editor failed")

        with patch(
            "zrb.llm.tool_call.edit_util.edit_content_via_editor",
            mock_edit_content_via_editor,
        ):
            result = await default_response_handler(ui, call, "edit", AsyncMock())

        assert result is None


class TestEditContentViaEditor:
    """Test edit_content_via_editor function."""

    @pytest.mark.asyncio
    async def test_edit_content_via_editor_creates_tempfile(self):
        """Test that edit_content_via_editor creates tempfile and calls editor."""
        from zrb.llm.tool_call.edit_util import edit_content_via_editor

        ui = MagicMock()
        ui.run_interactive_command = AsyncMock()

        content = {"command": "test", "args": ["--flag"]}

        result = await edit_content_via_editor(
            ui=ui,
            content=content,
            text_editor="cat",  # Use cat as safe editor
        )

        # Verify the content was read back (cat just outputs the content)
        assert result == content
