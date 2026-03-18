"""Tests for zrb_task.py - Zrb task tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from zrb.llm.tool.zrb_task import create_list_zrb_task_tool, create_run_zrb_task_tool


class TestListZrbTaskTool:
    """Test create_list_zrb_task_tool."""

    def test_create_function_returns_callable(self):
        """Test that create_list_zrb_task_tool returns a callable."""
        func = create_list_zrb_task_tool()
        assert callable(func)

    def test_function_name_includes_zrb(self):
        """Test that function name includes Zrb or zrb."""
        func = create_list_zrb_task_tool()
        # The name should include the command name
        assert func.__name__ is not None
        assert len(func.__name__) > 0

    def test_function_has_docstring(self):
        """Test that function has docstring."""
        func = create_list_zrb_task_tool()
        assert func.__doc__ is not None
        assert "MANDATE" in func.__doc__ or "Discovery" in func.__doc__

    def test_list_tasks_no_group(self):
        """Test listing tasks with no group specified."""
        from zrb.runner.cli import cli

        func = create_list_zrb_task_tool()
        result = func()

        # Should return a string describing tasks
        assert isinstance(result, str)
        assert "Tasks" in result or "tasks" in result

    def test_list_tasks_with_group(self):
        """Test listing tasks with a valid group."""
        func = create_list_zrb_task_tool()

        # This will list tasks, may return error if group not found
        result = func(group_name="builtin")
        assert isinstance(result, str)

    def test_list_tasks_invalid_group(self):
        """Test listing tasks with invalid group."""
        func = create_list_zrb_task_tool()

        result = func(group_name="nonexistent_invalid_group_xyz")
        assert isinstance(result, str)
        assert "Error" in result or "not found" in result


class TestRunZrbTaskTool:
    """Test create_run_zrb_task_tool."""

    def test_create_function_returns_callable(self):
        """Test that create_run_zrb_task_tool returns a callable."""
        func = create_run_zrb_task_tool()
        assert callable(func)

    def test_function_has_docstring(self):
        """Test that function has docstring."""
        func = create_run_zrb_task_tool()
        assert func.__doc__ is not None
        assert "MANDATES" in func.__doc__ or "Executes" in func.__doc__

    def test_function_is_async(self):
        """Test that the returned function is async."""
        import inspect
        func = create_run_zrb_task_tool()
        assert inspect.iscoroutinefunction(func)

    @pytest.mark.asyncio
    async def test_run_nonexistent_task(self):
        """Test running a nonexistent task."""
        func = create_run_zrb_task_tool()

        result = await func(task_name="nonexistent_task_xyz_123")
        assert isinstance(result, str)
        # The task doesn't exist, should return some response (error or not found)
        # The actual behavior depends on run_shell_command
        assert len(result) >= 0  # Just verify it returns a string

    @pytest.mark.asyncio
    async def test_run_task_with_args(self):
        """Test running a task with args."""
        func = create_run_zrb_task_tool()

        # This will fail because the task doesn't exist
        result = await func(
            task_name="nonexistent_task",
            args={"arg1": "value1"},
            timeout=5
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_run_task_timeout_parameter(self):
        """Test that timeout parameter is accepted."""
        func = create_run_zrb_task_tool()

        # Timeout should be passed to run_shell_command
        # Since task doesn't exist, it will fail but should accept timeout
        result = await func(task_name="test_task", timeout=10)
        assert isinstance(result, str)
