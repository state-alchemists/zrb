"""
Todo/Planning Tool for LLM Agents.

Implements task planning and progress tracking similar to Deep Agents' write_todos.

Storage:
- Todos are stored per conversation session
- Persisted to disk at ~/.zrb/todos/{session_name}.json
- Survives application restarts

Usage:
- write_todos: Create/replace todo list for planning
- get_todos: Get current todo list and progress
- update_todo: Update status of a single todo item
"""

from __future__ import annotations

import json
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from zrb.context.any_context import zrb_print

# Todo status types
TodoStatus = Literal["pending", "in_progress", "completed", "cancelled"]


class TodoManager:
    """
    Singleton manager for todo lists per conversation session.

    Features:
    - Per-session todo storage (isolated between conversations)
    - File persistence (survives restarts)
    - Progress tracking
    """

    _instance: TodoManager | None = None
    _todos: dict[str, dict[str, Any]]  # session_name -> todo_data
    _todo_dir: Path

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._todos = {}
            cls._instance._todo_dir = Path.home() / ".zrb" / "todos"
            cls._instance._todo_dir.mkdir(parents=True, exist_ok=True)
        return cls._instance

    def _get_todo_file(self, session_name: str) -> Path:
        """Get the file path for a session's todos."""
        # Sanitize session name for filesystem
        safe_name = "".join(
            c if c.isalnum() or c in "-_" else "_" for c in session_name
        )
        return self._todo_dir / f"{safe_name}.json"

    def _load_todos(self, session_name: str) -> dict[str, Any] | None:
        """Load todos from disk for a session."""
        if session_name in self._todos:
            return self._todos[session_name]

        todo_file = self._get_todo_file(session_name)
        if todo_file.exists():
            try:
                with open(todo_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._todos[session_name] = data
                    return data
            except Exception as e:
                zrb_print(
                    f"Warning: Failed to load todos for {session_name}: {e}", plain=True
                )
        return None

    def _save_todos(self, session_name: str) -> None:
        """Save todos to disk for a session."""
        if session_name not in self._todos:
            return

        todo_file = self._get_todo_file(session_name)
        try:
            with open(todo_file, "w", encoding="utf-8") as f:
                json.dump(self._todos[session_name], f, indent=2)
        except Exception as e:
            zrb_print(
                f"Warning: Failed to save todos for {session_name}: {e}", plain=True
            )

    @staticmethod
    def _compute_stats(new_todos: list[dict[str, Any]]) -> dict[str, int]:
        """Compute todo summary counts."""
        return {
            "total": len(new_todos),
            "completed": sum(1 for t in new_todos if t["status"] == "completed"),
            "in_progress": sum(1 for t in new_todos if t["status"] == "in_progress"),
            "pending": sum(1 for t in new_todos if t["status"] == "pending"),
            "cancelled": sum(1 for t in new_todos if t["status"] == "cancelled"),
        }

    @staticmethod
    def _build_todo_entry(
        todo: dict[str, Any],
        todo_id: str,
        existing: dict[str, dict[str, Any]] | None,
        replace: bool,
        now: str,
    ) -> dict[str, Any]:
        """Build a single todo entry, merging with existing if not replacing."""
        if existing and todo_id in existing and not replace:
            existing[todo_id].update(
                {
                    "content": todo.get("content", existing[todo_id]["content"]),
                    "status": todo.get("status", existing[todo_id]["status"]),
                }
            )
            return existing[todo_id]
        return {
            "id": todo_id,
            "content": todo.get("content", ""),
            "status": todo.get("status", "pending"),
            "created_at": now,
        }

    def write_todos(
        self,
        session_name: str,
        todos: list[dict[str, Any]],
        replace: bool = True,
    ) -> dict[str, Any]:
        """
        Write todos for a session.

        Returns:
            The updated todo list with metadata
        """
        now = datetime.now().isoformat()

        existing = self._load_todos(session_name) if not replace else None
        existing_todos = (
            {t["id"]: t for t in existing.get("todos", [])} if existing else {}
        )

        new_todos = []
        for i, todo in enumerate(todos):
            todo_id = todo.get("id") or str(i + 1)
            new_todos.append(
                self._build_todo_entry(todo, todo_id, existing_todos, replace, now)
            )

        # Include existing todos not in this update when merging
        if not replace and existing:
            seen = {t["id"] for t in new_todos}
            for tid, t in existing_todos.items():
                if tid not in seen:
                    new_todos.append(t)

        new_todos.sort(key=self._sort_key)

        stats = self._compute_stats(new_todos)
        result = {
            "todos": new_todos,
            "created_at": existing.get("created_at", now) if existing else now,
            "updated_at": now,
            **stats,
        }

        self._todos[session_name] = result
        self._save_todos(session_name)
        return result

    @staticmethod
    def _sort_key(t: dict[str, Any]) -> tuple[int, int | str]:
        try:
            return (0, int(t["id"]))
        except (ValueError, TypeError):
            return (1, t["id"])

    def get_todos(self, session_name: str) -> dict[str, Any] | None:
        """
        Get todos for a session.

        Returns:
            Todo list with metadata, or None if no todos exist
        """
        return self._load_todos(session_name)

    def update_todo(
        self,
        session_name: str,
        todo_id: str,
        status: TodoStatus | None = None,
        content: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Update a single todo item.

        Returns:
            The updated todo list, or None if not found
        """
        todos_data = self._load_todos(session_name)
        if not todos_data:
            return None

        now = datetime.now().isoformat()
        found = False

        for todo in todos_data.get("todos", []):
            if todo["id"] == todo_id:
                if status is not None:
                    todo["status"] = status
                if content is not None:
                    todo["content"] = content
                todo["updated_at"] = now
                found = True
                break

        if not found:
            return None

        # Update counts
        todos_data["completed"] = sum(
            1 for t in todos_data["todos"] if t["status"] == "completed"
        )
        todos_data["in_progress"] = sum(
            1 for t in todos_data["todos"] if t["status"] == "in_progress"
        )
        todos_data["pending"] = sum(
            1 for t in todos_data["todos"] if t["status"] == "pending"
        )
        todos_data["cancelled"] = sum(
            1 for t in todos_data["todos"] if t["status"] == "cancelled"
        )
        todos_data["updated_at"] = now

        self._todos[session_name] = todos_data
        self._save_todos(session_name)

        return todos_data

    def clear_todos(self, session_name: str) -> bool:
        """Clear todos for a session."""
        if session_name in self._todos:
            del self._todos[session_name]

        todo_file = self._get_todo_file(session_name)
        if todo_file.exists():
            try:
                todo_file.unlink()
                return True
            except Exception:
                return False
        return True


# Singleton instance
todo_manager = TodoManager()


_current_session: ContextVar[str] = ContextVar("zrb_current_session", default="default")


def get_current_context_session() -> str:
    """Get the current session name, set by set_current_session() before agent runs."""
    return _current_session.get()


def set_current_session(session_name: str) -> None:
    """Set the current session name so todo tools use the right session automatically."""
    if session_name:
        _current_session.set(session_name)


# Tool functions for LLM integration


async def write_todos(
    todos: list[dict[str, Any]],
    session: str = "",
    replace: bool = True,
) -> str:
    """
    Creates or replaces the todo list for the current session.

    With `replace=True` (default), all existing todos are overwritten. Pass `replace=False` to merge.
    """
    session_name = session or get_current_context_session()

    result = todo_manager.write_todos(session_name, todos, replace)

    # Format compactly — no emoji, clear structure
    lines = [
        f"[{session_name}] {result['completed']}/{result['total']} done, {result['in_progress']} in progress"
    ]
    for todo in result["todos"]:
        status_char = {
            "completed": "[+]",
            "in_progress": "[>]",
            "pending": "[ ]",
            "cancelled": "[-]",
        }.get(todo["status"], "[?]")
        lines.append(f"  {status_char} [{todo['id']}] {todo['content']}")

    lines.append("\nUse `update_todo` to change status; `get_todos` to check state.")

    return "\n".join(lines)


async def get_todos(session: str = "") -> str:
    """
    Returns the current todo list and progress summary.

    Check before starting a subtask and before declaring work done.
    """
    session_name = session or get_current_context_session()

    result = todo_manager.get_todos(session_name)

    if not result or not result.get("todos"):
        return f"No todos for session '{session_name}'. Use `write_todos` to create a plan."

    # Format compactly — no emoji, clear structure
    lines = [
        f"[{session_name}] Progress: {result['completed']}/{result['total']} done, {result['in_progress']} in progress, {result['pending']} pending"
    ]
    lines.append(
        f"Updated: {result.get('updated_at', result.get('created_at', 'N/A'))}"
    )
    for todo in result["todos"]:
        status_char = {
            "completed": "[+]",
            "in_progress": "[>]",
            "pending": "[ ]",
            "cancelled": "[-]",
        }.get(todo["status"], "[?]")
        lines.append(
            f"  {status_char} [{todo['id']}] {todo['content']} -> {todo['status']}"
        )

    if result["total"] > 0:
        progress = (result["completed"] / result["total"]) * 100
        lines.append(f"\nProgress: {progress:.0f}%")

    return "\n".join(lines)


async def update_todo(
    todo_id: str,
    status: TodoStatus | None = None,
    content: str | None = None,
    session: str = "",
) -> str:
    """
    Updates the status or content of a single todo item.

    Status values: "pending", "in_progress", "completed", "cancelled".
    Mark "in_progress" before starting work, "completed" after finishing.
    """
    session_name = session or get_current_context_session()

    if status is None and content is None:
        return (
            "Error: Must provide 'status' and/or 'content' to update.\n"
            "[SYSTEM SUGGESTION]: Provide at least one of status "
            "(pending/in_progress/completed/cancelled) or content."
        )

    result = todo_manager.update_todo(session_name, todo_id, status, content)

    if not result:
        return (
            f"Error: Todo '{todo_id}' not found in session '{session_name}'.\n"
            f"[SYSTEM SUGGESTION]: Use `get_todos` to see valid todo IDs."
        )

    # Find the updated todo
    updated_todo = None
    for todo in result["todos"]:
        if todo["id"] == todo_id:
            updated_todo = todo
            break

    if not updated_todo:
        return f"Error: Todo '{todo_id}' not found. Use `get_todos` to see valid IDs."

    # Compact format
    lines = [
        f"[{session_name}] Updated: [{todo_id}] {updated_todo['content']} -> {updated_todo['status']}"
    ]
    lines.append(
        f"Progress: {result['completed']}/{result['total']} done, {result['in_progress']} in progress"
    )

    # Show remaining tasks compactly
    pending = [t for t in result["todos"] if t["status"] == "pending"]
    in_progress = [t for t in result["todos"] if t["status"] == "in_progress"]

    if in_progress:
        lines.append(
            "In progress: "
            + ", ".join(f"[{t['id']}] {t['content']}" for t in in_progress)
        )

    if pending:
        lines.append(
            "Pending: " + ", ".join(f"[{t['id']}] {t['content']}" for t in pending)
        )

    return "\n".join(lines)


async def clear_todos(session: str = "") -> str:
    """
    Clears all todos for the current session. Use only when starting a completely new plan.
    """
    session_name = session or get_current_context_session()

    success = todo_manager.clear_todos(session_name)

    if success:
        return f"Cleared all todos for session '{session_name}'."
    return f"No todos to clear for session '{session_name}'."


# Export tool functions with proper names for LLM
write_todos.__name__ = "WriteTodos"
get_todos.__name__ = "GetTodos"
update_todo.__name__ = "UpdateTodo"
clear_todos.__name__ = "ClearTodos"


def create_plan_tools() -> list:
    """Create planning tools for registration with LLM agent."""
    return [write_todos, get_todos, update_todo, clear_todos]
