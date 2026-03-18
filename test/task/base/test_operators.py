"""Tests for task/base/operators.py - Task operator handling."""

import pytest
from unittest.mock import MagicMock, patch


class TestHandleRshift:
    """Test handle_rshift function."""

    def test_rshift_single_task(self):
        """Test >> operator with single task."""
        from zrb.task.base.operators import handle_rshift

        left_task = MagicMock()
        right_task = MagicMock()

        result = handle_rshift(left_task, right_task)

        right_task.append_upstream.assert_called_once_with(left_task)
        assert result == right_task

    def test_rshift_task_list(self):
        """Test >> operator with list of tasks."""
        from zrb.task.base.operators import handle_rshift

        left_task = MagicMock()
        right_task1 = MagicMock()
        right_task2 = MagicMock()

        result = handle_rshift(left_task, [right_task1, right_task2])

        right_task1.append_upstream.assert_called_once_with(left_task)
        right_task2.append_upstream.assert_called_once_with(left_task)
        assert result == [right_task1, right_task2]

    def test_rshift_error_handling(self):
        """Test >> operator error handling."""
        from zrb.task.base.operators import handle_rshift

        left_task = MagicMock()
        right_task = MagicMock()
        right_task.append_upstream.side_effect = Exception("Test error")

        with pytest.raises(ValueError) as exc_info:
            handle_rshift(left_task, right_task)

        assert "Invalid operation" in str(exc_info.value)
        assert "Test error" in str(exc_info.value)

    def test_rshift_empty_list(self):
        """Test >> operator with empty list."""
        from zrb.task.base.operators import handle_rshift

        left_task = MagicMock()

        result = handle_rshift(left_task, [])

        assert result == []


class TestHandleLshift:
    """Test handle_lshift function."""

    def test_lshift_single_task(self):
        """Test << operator with single task."""
        from zrb.task.base.operators import handle_lshift

        left_task = MagicMock()
        right_task = MagicMock()

        result = handle_lshift(left_task, right_task)

        left_task.append_upstream.assert_called_once_with(right_task)
        assert result == left_task

    def test_lshift_task_list(self):
        """Test << operator with list of tasks."""
        from zrb.task.base.operators import handle_lshift

        left_task = MagicMock()
        right_tasks = [MagicMock(), MagicMock()]

        result = handle_lshift(left_task, right_tasks)

        left_task.append_upstream.assert_called_once_with(right_tasks)
        assert result == left_task

    def test_lshift_error_handling(self):
        """Test << operator error handling."""
        from zrb.task.base.operators import handle_lshift

        left_task = MagicMock()
        right_task = MagicMock()
        left_task.append_upstream.side_effect = Exception("Test error")

        with pytest.raises(ValueError) as exc_info:
            handle_lshift(left_task, right_task)

        assert "Invalid operation" in str(exc_info.value)
        assert "Test error" in str(exc_info.value)

    def test_lshift_returns_left_task(self):
        """Test << operator returns left task."""
        from zrb.task.base.operators import handle_lshift

        left_task = MagicMock(name="left")
        right_task = MagicMock(name="right")

        result = handle_lshift(left_task, right_task)

        assert result == left_task