"""Tests for plan.py - Todo management tools."""

import pytest

from zrb.llm.tool.ambient_state import get_current_context_session, set_current_session
from zrb.llm.tool.plan import (
    TodoManager,
    create_plan_tools,
    get_todos,
    todo_manager,
    write_todos,
)


class TestUtilityFunctions:
    """Test utility functions."""

    def test_get_current_context_session(self):
        """Test get_current_context_session returns a string."""
        result = get_current_context_session()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_set_current_session_changes_get_result(self):
        """set_current_session should change what get_current_context_session returns."""
        import uuid

        unique = f"test-session-{uuid.uuid4().hex[:8]}"
        set_current_session(unique)
        try:
            assert get_current_context_session() == unique
        finally:
            # set_current_session has no scoped/reset counterpart (see
            # zrb.util.contextvar_scope) — an unset value here leaks into
            # every later test in this worker process, which once broke
            # unrelated tests (e.g. test_delegate_tool.py) that assume the
            # ambient session defaults to "default".
            set_current_session("default")

    def test_set_current_session_ignores_empty_string(self):
        """set_current_session with empty string should not overwrite the current value."""
        import uuid

        unique = f"test-session-{uuid.uuid4().hex[:8]}"
        set_current_session(unique)
        try:
            set_current_session("")  # should be a no-op
            assert get_current_context_session() == unique
        finally:
            set_current_session("default")

    @pytest.mark.asyncio
    async def test_todo_tools_use_session_from_set_current_session(self, tmp_path):
        """Todo tools called without session= should use the value from set_current_session."""
        manager = TodoManager()
        manager.todo_dir = tmp_path
        manager.todos = {}

        import uuid

        session = f"ctx-session-{uuid.uuid4().hex[:8]}"
        set_current_session(session)
        try:
            await write_todos([{"content": "Auto-session task"}])
            result = await get_todos()

            assert session in result
            assert "Auto-session task" in result
        finally:
            set_current_session("default")

    def test_create_plan_tools(self):
        """Agent-facing plan tools are TodoWrite + TodoRead.

        TodoWrite replaces the list by default, so it subsumes the former
        per-item update and clear operations.
        """
        tools = create_plan_tools()

        names = [t.__name__ for t in tools]
        assert names == ["TodoWrite", "TodoRead"]

    def test_todo_manager_instance(self):
        """Test that todo_manager is a TodoManager instance."""
        assert isinstance(todo_manager, TodoManager)


class TestTodoStatusValues:
    """Test different todo status values."""

    @pytest.mark.asyncio
    async def test_all_status_values(self, tmp_path):
        """Test all valid status values."""
        manager = TodoManager()
        manager.todo_dir = tmp_path
        manager.todos = {}

        for status in ["pending", "in_progress", "completed", "cancelled"]:
            todos = [{"content": f"Task with {status}", "status": status}]
            result = await write_todos(todos, session=f"{status}_session")
            assert status in result or "pending" in result

    @pytest.mark.asyncio
    async def test_status_counts_accuracy(self, tmp_path):
        """Test that status counts are accurate."""
        manager = TodoManager()
        manager.todo_dir = tmp_path
        manager.todos = {}

        import uuid

        unique_session = f"counts_{uuid.uuid4().hex[:8]}"

        todos = [
            {"content": "Pending 1", "status": "pending"},
            {"content": "Pending 2", "status": "pending"},
            {"content": "Progress 1", "status": "in_progress"},
            {"content": "Completed 1", "status": "completed"},
            {"content": "Cancelled 1", "status": "cancelled"},
        ]

        await write_todos(todos, session=unique_session)
        result = await get_todos(session=unique_session)

        # Check the new compact format
        assert "2 pending" in result
        assert "1 in progress" in result
        assert "[+]" in result  # completed items use [+]
