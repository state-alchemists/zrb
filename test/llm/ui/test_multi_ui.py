"""Tests for multi_ui.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMultiUI:
    def test_initialization(self):
        from zrb.llm.ui.multi_ui import MultiUI

        mock_ui = MagicMock()
        multi = MultiUI([mock_ui])
        assert len(multi._uis) == 1
        assert multi._main_ui_index == 0
        assert multi._message_queue is not None

    def test_initialization_with_multiple_uis(self):
        from zrb.llm.ui.multi_ui import MultiUI

        mock_ui1 = MagicMock()
        mock_ui2 = MagicMock()
        multi = MultiUI([mock_ui1, mock_ui2], main_ui_index=1)
        assert len(multi._uis) == 2
        assert multi._main_ui_index == 1

    def test_sets_parent_reference(self):
        from zrb.llm.ui.multi_ui import MultiUI

        mock_ui = MagicMock()
        MultiUI([mock_ui])
        assert hasattr(mock_ui, "_multi_ui_parent")

    def test_main_ui_property(self):
        from zrb.llm.ui.multi_ui import MultiUI

        mock_ui1 = MagicMock()
        mock_ui2 = MagicMock()
        multi = MultiUI([mock_ui1, mock_ui2], main_ui_index=1)
        assert multi._main_ui == mock_ui2

    def test_main_ui_property_empty(self):
        from zrb.llm.ui.multi_ui import MultiUI

        multi = MultiUI([])
        assert multi._main_ui is None

    def test_set_llm_task(self):
        from zrb.llm.ui.multi_ui import MultiUI

        mock_ui = MagicMock()
        mock_ui2 = MagicMock()
        multi = MultiUI([mock_ui, mock_ui2])
        mock_task = MagicMock()
        multi.set_llm_task(mock_task)
        assert multi._llm_task is mock_task

    def test_set_llm_task_sets_on_children(self):
        from zrb.llm.ui.multi_ui import MultiUI

        mock_ui = MagicMock(spec=["llm_task"])
        mock_ui2 = MagicMock(spec=["llm_task"])
        multi = MultiUI([mock_ui, mock_ui2])
        mock_task = MagicMock()
        multi.set_llm_task(mock_task)
        assert mock_ui.llm_task is mock_task
        assert mock_ui2.llm_task is mock_task

    def test_set_tool_call_handler(self):
        from zrb.llm.ui.multi_ui import MultiUI

        mock_ui = MagicMock()
        multi = MultiUI([mock_ui])
        mock_handler = MagicMock()
        multi.set_tool_call_handler(mock_handler)
        assert multi.tool_call_handler is mock_handler

    def test_set_approval_channel(self):
        from zrb.llm.ui.multi_ui import MultiUI

        mock_ui = MagicMock()
        multi = MultiUI([mock_ui])
        mock_channel = MagicMock()
        multi.set_approval_channel(mock_channel)
        assert multi._approval_channel is mock_channel

    def test_append_to_output_broadcasts_to_all(self):
        from zrb.llm.ui.multi_ui import MultiUI

        mock_ui1 = MagicMock()
        mock_ui2 = MagicMock()
        multi = MultiUI([mock_ui1, mock_ui2])
        multi.append_to_output("Hello", "World")
        mock_ui1.append_to_output.assert_called_once()
        mock_ui2.append_to_output.assert_called_once()

    def test_append_to_output_handles_exception(self):
        from zrb.llm.ui.multi_ui import MultiUI

        mock_ui1 = MagicMock()
        mock_ui1.append_to_output.side_effect = Exception("test error")
        mock_ui2 = MagicMock()
        multi = MultiUI([mock_ui1, mock_ui2])
        # Should not raise
        multi.append_to_output("Hello")

    def test_last_output_property(self):
        from zrb.llm.ui.multi_ui import MultiUI

        mock_ui = MagicMock()
        multi = MultiUI([mock_ui])
        multi.last_output = "test output"
        assert multi.last_output == "test output"

    def test_set_llm_task_with_ui_without_llm_task_attr(self):
        from zrb.llm.ui.multi_ui import MultiUI

        mock_ui = MagicMock(spec=[])
        multi = MultiUI([mock_ui])
        mock_task = MagicMock()
        # Should not raise even if UI doesn't have llm_task
        multi.set_llm_task(mock_task)

    def test_tool_call_handler_property(self):
        from zrb.llm.ui.multi_ui import MultiUI

        mock_ui = MagicMock()
        multi = MultiUI([mock_ui])
        assert multi.tool_call_handler is None

    def test_initialization_sets_attributes(self):
        from zrb.llm.ui.multi_ui import MultiUI

        mock_ui = MagicMock()
        multi = MultiUI([mock_ui])
        assert multi._responses == {}
        assert multi._shutdown_event is None
        assert multi._child_tasks == []
        assert multi._pending_input_tasks == []
        assert multi._process_messages_task is None
        assert multi._running_llm_task is None
        assert multi._is_thinking is False
        assert multi._last_result_data is None
        assert multi._approval_channel is None
        assert multi._last_winning_ui is None
        assert multi._tool_call_handler is None
