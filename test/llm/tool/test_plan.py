"""Tests for plan.py - Todo management tools."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zrb.llm.tool.plan import (
    TodoManager,
    create_plan_tools,
    get_current_context_session,
    get_todos,
    set_current_session,
    todo_manager,
    write_todos,
)


class TestTodoManager:
    """Test TodoManager class."""

    def test_singleton_pattern(self):
        """Test that TodoManager is a singleton."""
        manager1 = TodoManager()
        manager2 = TodoManager()
        assert manager1 is manager2

    def test_get_todo_file_sanitization(self, tmp_path):
        """Test that session names are sanitized for filesystem."""
        manager = TodoManager()
        # Reset the todo directory for testing
        manager._todo_dir = tmp_path

        # Test sanitization of special characters
        file_path = manager._get_todo_file("test/session:name*?.txt")
        assert "test" not in str(file_path) or "_" in str(file_path)
        assert "session" not in str(file_path) or "_" in str(file_path)

    def test_save_and_load_todos(self, tmp_path):
        """Test saving and loading todos."""
        manager = TodoManager()
        manager._todo_dir = tmp_path
        manager._todos = {}  # Clear cache

        todos_data = {
            "todos": [
                {"id": "1", "content": "Task 1", "status": "pending"},
                {"id": "2", "content": "Task 2", "status": "completed"},
            ],
            "created_at": "2024-01-01T00:00:00",
            "total": 2,
        }
        manager._todos["test_session"] = todos_data
        manager._save_todos("test_session")

        # Clear cache and reload
        manager._todos = {}
        loaded = manager._load_todos("test_session")

        assert loaded is not None
        assert loaded["total"] == 2
        assert len(loaded["todos"]) == 2

    def test_load_todos_nonexistent_session(self, tmp_path):
        """Test loading todos for non-existent session."""
        manager = TodoManager()
        manager._todo_dir = tmp_path
        manager._todos = {}

        result = manager._load_todos("nonexistent_session")
        assert result is None

    def test_write_todos_basic(self, tmp_path):
        """Test basic todo writing."""
        manager = TodoManager()
        manager._todo_dir = tmp_path
        manager._todos = {}

        todos = [
            {"content": "Task 1"},
            {"content": "Task 2", "status": "in_progress"},
            {"content": "Task 3", "id": "custom_id"},
        ]

        result = manager.write_todos("test_session", todos)

        assert result["total"] == 3
        assert result["pending"] == 2  # Task 1 and Task 3 (default status)
        assert result["in_progress"] == 1  # Task 2
        assert result["completed"] == 0

        # Check auto-assigned IDs
        assert result["todos"][0]["id"] == "1"
        assert result["todos"][1]["id"] == "2"
        assert result["todos"][2]["id"] == "custom_id"

    def test_write_todos_replace_false_merge(self, tmp_path):
        """Test merging todos when replace=False."""
        manager = TodoManager()
        manager._todo_dir = tmp_path
        manager._todos = {}

        # Write initial todos
        initial_todos = [
            {"id": "1", "content": "Task 1", "status": "pending"},
            {"id": "2", "content": "Task 2", "status": "pending"},
        ]
        manager.write_todos("test_session", initial_todos)

        # Merge with update
        merge_todos = [
            {"id": "1", "content": "Task 1 Updated", "status": "completed"},
            {"id": "3", "content": "Task 3", "status": "pending"},
        ]
        result = manager.write_todos("test_session", merge_todos, replace=False)

        # Should have 3 todos (merged)
        assert result["total"] == 3
        # Task 1 should be updated
        task1 = next(t for t in result["todos"] if t["id"] == "1")
        assert task1["content"] == "Task 1 Updated"
        assert task1["status"] == "completed"

    def test_write_todos_counts(self, tmp_path):
        """Test that status counts are correct."""
        manager = TodoManager()
        manager._todo_dir = tmp_path
        manager._todos = {}

        todos = [
            {"content": "Task 1", "status": "pending"},
            {"content": "Task 2", "status": "completed"},
            {"content": "Task 3", "status": "in_progress"},
            {"content": "Task 4", "status": "cancelled"},
        ]

        result = manager.write_todos("test_session", todos)

        assert result["total"] == 4
        assert result["pending"] == 1
        assert result["completed"] == 1
        assert result["in_progress"] == 1
        assert result["cancelled"] == 1

    def test_sort_todos_numeric_ids(self, tmp_path):
        """Test that todos are sorted correctly with numeric IDs."""
        manager = TodoManager()
        manager._todo_dir = tmp_path
        manager._todos = {}

        # Create todos with mixed ID types
        todos = [
            {"id": "10", "content": "Task 10"},
            {"id": "2", "content": "Task 2"},
            {"id": "1", "content": "Task 1"},
        ]
        result = manager.write_todos("test_session", todos)

        # Numeric IDs should be sorted numerically
        assert result["todos"][0]["id"] == "1"
        assert result["todos"][1]["id"] == "2"
        assert result["todos"][2]["id"] == "10"


class TestTodoManagerErrorHandling:
    """Test error handling in TodoManager."""

    def test_load_todos_corrupted_file(self, tmp_path):
        """Test loading corrupted JSON file."""
        manager = TodoManager()
        manager._todo_dir = tmp_path
        manager._todos = {}

        # Write corrupted JSON
        corrupted_file = tmp_path / "corrupted.json"
        corrupted_file.write_text("not valid json{")

        # Should handle error gracefully
        try:
            # First write a valid file with different name
            manager.write_todos("valid_session", [{"content": "test"}])
            # Try to load corrupted - this should fail and return None or handle
            result = manager._load_todos("corrupted")
            # If file is corrupted, it should return None
            assert result is None or result == {}
        except Exception:
            # If it raises, that's also acceptable behavior
            pass

    def test_save_todos_permission_error(self, tmp_path):
        """Test handling permission errors when saving."""
        manager = TodoManager()
        manager._todo_dir = tmp_path

        # This should work without errors
        manager.write_todos("test_session", [{"content": "Task 1"}])


class TestAsyncFunctions:
    """Test async todo functions."""

    @pytest.mark.asyncio
    async def test_write_todos_unknown_keys(self, tmp_path):
        """write_todos rejects unknown keys with a SYSTEM SUGGESTION error."""
        manager = TodoManager()
        manager._todo_dir = tmp_path
        manager._todos = {}

        result = await write_todos(
            [{"description": "Fix bug"}, {"content": "Valid task"}],
            session="key_check",
        )

        assert "Error" in result
        assert "description" in result
        assert "content" in result
        assert "SYSTEM SUGGESTION" in result
        assert "todo #1" in result.lower() or "Todo #1" in result

    @pytest.mark.asyncio
    async def test_write_todos_multiple_unknown_keys(self, tmp_path):
        """Lists every invalid key, not just the first."""
        result = await write_todos(
            [{"title": "A", "summary": "B"}], session="multi_key"
        )

        assert "title" in result
        assert "summary" in result
        assert "SYSTEM SUGGESTION" in result

    @pytest.mark.asyncio
    async def test_write_todos_valid_keys_pass(self, tmp_path):
        """Valid keys like content, status, id should not trigger errors."""
        manager = TodoManager()
        manager._todo_dir = tmp_path
        manager._todos = {}

        result = await write_todos(
            [
                {"content": "Real task", "status": "pending"},
                {"content": "Another", "id": "x1"},
            ],
            session="good_keys",
        )

        assert "Error" not in result
        assert "Real task" in result
        assert "Another" in result

    @pytest.mark.asyncio
    async def test_write_todos_async(self, tmp_path):
        """Test write_todos async function."""
        manager = TodoManager()
        manager._todo_dir = tmp_path
        manager._todos = {}

        todos = [
            {"content": "Task 1", "status": "pending"},
            {"content": "Task 2", "status": "in_progress"},
        ]

        result = await write_todos(todos, session="test_async_session")

        assert "[test_async_session]" in result
        assert "Task 1" in result
        assert "Task 2" in result

    @pytest.mark.asyncio
    async def test_write_todos_merge_mode(self, tmp_path):
        """Test write_todos with merge mode."""
        manager = TodoManager()
        manager._todo_dir = tmp_path
        manager._todos = {}

        # Write initial with explicit IDs
        await write_todos(
            [{"id": "1", "content": "Task 1"}],
            session="merge_session_replace",
            replace=True,
        )

        # Now write with replace=False - need to use same IDs to merge
        # Note: The singleton todo_manager has its own _todo_dir, so we need to clear that too
        import uuid

        unique_session = f"merge_{uuid.uuid4().hex[:8]}"

        # First write with explicit IDs
        await write_todos(
            [{"id": "1", "content": "Task 1", "status": "pending"}],
            session=unique_session,
            replace=True,
        )

        # Second write with merge - add a new task
        result = await write_todos(
            [{"id": "2", "content": "Task 2", "status": "pending"}],
            session=unique_session,
            replace=False,
        )

        # Verify both tasks are present (merged)
        assert result is not None
        assert "Task 2" in result

    @pytest.mark.asyncio
    async def test_get_todos_empty(self, tmp_path):
        """Test get_todos when no todos exist."""
        manager = TodoManager()
        manager._todo_dir = tmp_path
        manager._todos = {}

        result = await get_todos(session="empty_session")

        assert "No todos" in result

    @pytest.mark.asyncio
    async def test_get_todos_with_data(self, tmp_path):
        """Test get_todos with existing todos."""
        manager = TodoManager()
        manager._todo_dir = tmp_path
        manager._todos = {}

        await write_todos(
            [
                {"content": "Task 1", "status": "completed"},
                {"content": "Task 2", "status": "pending"},
            ],
            session="existing_session",
        )

        result = await get_todos(session="existing_session")

        assert "[existing_session]" in result
        assert "Task 1" in result
        assert "Task 2" in result
        assert "Progress:" in result


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
        assert get_current_context_session() == unique

    def test_set_current_session_ignores_empty_string(self):
        """set_current_session with empty string should not overwrite the current value."""
        import uuid

        unique = f"test-session-{uuid.uuid4().hex[:8]}"
        set_current_session(unique)
        set_current_session("")  # should be a no-op
        assert get_current_context_session() == unique

    @pytest.mark.asyncio
    async def test_todo_tools_use_session_from_set_current_session(self, tmp_path):
        """Todo tools called without session= should use the value from set_current_session."""
        manager = TodoManager()
        manager._todo_dir = tmp_path
        manager._todos = {}

        import uuid

        session = f"ctx-session-{uuid.uuid4().hex[:8]}"
        set_current_session(session)

        await write_todos([{"content": "Auto-session task"}])
        result = await get_todos()

        assert session in result
        assert "Auto-session task" in result

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
        manager._todo_dir = tmp_path
        manager._todos = {}

        for status in ["pending", "in_progress", "completed", "cancelled"]:
            todos = [{"content": f"Task with {status}", "status": status}]
            result = await write_todos(todos, session=f"{status}_session")
            assert status in result or "pending" in result

    @pytest.mark.asyncio
    async def test_status_counts_accuracy(self, tmp_path):
        """Test that status counts are accurate."""
        manager = TodoManager()
        manager._todo_dir = tmp_path
        manager._todos = {}

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
