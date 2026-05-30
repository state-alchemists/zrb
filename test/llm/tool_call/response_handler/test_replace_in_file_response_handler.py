"""Tests for replace_in_file_response_handler.py."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestReplaceInFileResponseHandler:
    """Test replace_in_file_response_handler function."""

    @pytest.mark.asyncio
    async def test_non_edit_tool_passes_through(self):
        """Test that non-Edit tools pass through to next handler."""
        from zrb.llm.tool_call.response_handler.replace_in_file_response_handler import (
            replace_in_file_response_handler,
        )

        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "Write"
        call.args = {"path": "test.txt"}

        next_handler = AsyncMock(return_value="passed_through")

        result = await replace_in_file_response_handler(ui, call, "edit", next_handler)

        assert result == "passed_through"
        next_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_edit_response_passes_through(self):
        """Test that non-edit responses pass through to next handler."""
        from zrb.llm.tool_call.response_handler.replace_in_file_response_handler import (
            replace_in_file_response_handler,
        )

        ui = MagicMock()
        call = MagicMock()
        call.tool_name = "Edit"
        call.args = {"old_text": "old", "new_text": "new"}

        next_handler = AsyncMock(return_value="passed_through")

        result = await replace_in_file_response_handler(ui, call, "yes", next_handler)

        assert result == "passed_through"
        next_handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_args_as_string(self):
        """Test handling string args."""
        from zrb.llm.tool_call.response_handler.replace_in_file_response_handler import (
            replace_in_file_response_handler,
        )

        ui = MagicMock()
        ui.run_interactive_command = AsyncMock()

        call = MagicMock()
        call.tool_name = "Edit"
        call.args = json.dumps({"old_text": "old content", "new_text": "new content"})

        next_handler = AsyncMock()

        result = await replace_in_file_response_handler(ui, call, "e", next_handler)
        # Result is None if no changes made
        assert result is None or hasattr(result, "override_args")

    @pytest.mark.asyncio
    async def test_edit_no_changes_returns_none(self):
        """Test edit with no changes returns None."""
        from zrb.llm.tool_call.response_handler.replace_in_file_response_handler import (
            replace_in_file_response_handler,
        )

        ui = MagicMock()
        ui.run_interactive_command = AsyncMock()

        call = MagicMock()
        call.tool_name = "Edit"
        call.args = {"old_text": "unchanged", "new_text": "unchanged"}

        next_handler = AsyncMock()

        result = await replace_in_file_response_handler(ui, call, "edit", next_handler)
        # No changes made, should return None
        assert result is None

    @pytest.mark.asyncio
    async def test_edit_with_args_dict(self):
        """Test edit with dictionary args."""
        from zrb.llm.tool_call.response_handler.replace_in_file_response_handler import (
            replace_in_file_response_handler,
        )

        ui = MagicMock()
        ui.run_interactive_command = AsyncMock()

        call = MagicMock()
        call.tool_name = "Edit"
        call.args = {"old_text": "text before", "new_text": "text after"}

        next_handler = AsyncMock()

        result = await replace_in_file_response_handler(ui, call, "e", next_handler)

        # Result depends on whether changes were made
        # In our case with mock, run_interactive_command won't modify the file
        # so it should return None
        assert result is None or hasattr(result, "override_args")


class TestReplaceInFileHandlerEdgeCases:
    """Test edge cases for replace_in_file_response_handler."""

    @pytest.mark.asyncio
    async def test_empty_new_text(self):
        """Test with empty new text."""
        from zrb.llm.tool_call.response_handler.replace_in_file_response_handler import (
            replace_in_file_response_handler,
        )

        ui = MagicMock()
        ui.run_interactive_command = AsyncMock()

        call = MagicMock()
        call.tool_name = "Edit"
        call.args = {"old_text": "something", "new_text": ""}

        next_handler = AsyncMock()

        result = await replace_in_file_response_handler(ui, call, "edit", next_handler)

        # Should handle empty new_text gracefully
        assert result is None or hasattr(result, "override_args")

    @pytest.mark.asyncio
    async def test_non_dict_args(self):
        """Test with non-dict args."""
        from zrb.llm.tool_call.response_handler.replace_in_file_response_handler import (
            replace_in_file_response_handler,
        )

        ui = MagicMock()
        ui.run_interactive_command = AsyncMock()

        call = MagicMock()
        call.tool_name = "Edit"
        call.args = ["not", "a", "dict"]  # list instead of dict

        next_handler = AsyncMock(return_value="passed")

        result = await replace_in_file_response_handler(ui, call, "edit", next_handler)

        # Should pass through to next handler
        assert result == "passed"

    @pytest.mark.asyncio
    async def test_args_string_that_is_invalid_json_falls_through(self):
        """A non-JSON string args still gets handled via the next handler."""
        from zrb.llm.tool_call.response_handler.replace_in_file_response_handler import (
            replace_in_file_response_handler,
        )

        ui = MagicMock()
        ui.run_interactive_command = AsyncMock()

        call = MagicMock()
        call.tool_name = "Edit"
        call.args = "not-json-at-all"

        next_handler = AsyncMock(return_value="fell_through")
        result = await replace_in_file_response_handler(ui, call, "e", next_handler)
        # Args stay a string (json.loads raised, swallowed), then non-dict → next
        assert result == "fell_through"

    @pytest.mark.asyncio
    async def test_edit_returns_tool_approved_when_user_modifies_new_text(self):
        """The diff-edit cmd modifies the new file → handler returns ToolApproved with
        the overridden args."""
        from zrb.llm.tool_call.response_handler.replace_in_file_response_handler import (
            replace_in_file_response_handler,
        )

        ui = MagicMock()

        async def fake_run(cmd, shell=False):
            # Find the .new file in the cmd and overwrite it
            for token in cmd.split():
                if token.endswith(".new"):
                    with open(token, "w", encoding="utf-8") as f:
                        f.write("EDITED")

        ui.run_interactive_command = AsyncMock(side_effect=fake_run)

        call = MagicMock()
        call.tool_name = "Edit"
        call.args = {"old_text": "before", "new_text": "after"}

        next_handler = AsyncMock()
        with patch(
            "zrb.llm.tool_call.response_handler.replace_in_file_response_handler.CFG"
        ) as mock_cfg:
            mock_cfg.DIFF_EDIT_COMMAND_TPL = "cp {new} {old}.bak && echo {new}"
            result = await replace_in_file_response_handler(ui, call, "e", next_handler)
        assert result is not None
        assert getattr(result, "override_args", None) == {
            "old_text": "before",
            "new_text": "EDITED",
        }

    @pytest.mark.asyncio
    async def test_exception_during_diff_returns_none(self):
        """If the diff command raises, the handler logs and returns None."""
        from zrb.llm.tool_call.response_handler.replace_in_file_response_handler import (
            replace_in_file_response_handler,
        )

        ui = MagicMock()
        ui.run_interactive_command = AsyncMock(
            side_effect=RuntimeError("diff exploded")
        )

        call = MagicMock()
        call.tool_name = "Edit"
        call.args = {"old_text": "a", "new_text": "b"}

        next_handler = AsyncMock()
        result = await replace_in_file_response_handler(ui, call, "e", next_handler)
        assert result is None
        # Error message gets surfaced to the UI
        appended = " ".join(
            c.args[0] for c in ui.append_to_output.call_args_list if c.args
        )
        assert "diff exploded" in appended
