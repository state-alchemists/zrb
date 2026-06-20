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

    def get_todos(self, session_name: str) -> dict[str, Any] | None:
        """
        Get todos for a session.

        Returns:
            Todo list with metadata, or None if no todos exist
        """
        return self._load_todos(session_name)

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

    @staticmethod
    def _sort_key(t: dict[str, Any]) -> tuple[int, int | str]:
        try:
            return (0, int(t["id"]))
        except (ValueError, TypeError):
            return (1, t["id"])


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


# ── Progress visualization ─────────────────────────────────────────────────


_STATUS_ICONS = {
    "completed": "✅",
    "in_progress": "▶️",
    "pending": "  ",
    "cancelled": "✗",
}


def _render_todo_progress(
    todo_data: dict[str, Any],
    change_description: str = "",
) -> str:
    """Render the full todo list for UI display.

    Shows what changed (if anything), a progress summary, and every todo item
    with its status icon.  Ends with a ``~DATA~`` line carrying structured JSON
    for the web frontend.
    """
    total = todo_data["total"]
    done = todo_data["completed"]
    pct = f"{int((done / total) * 100)}%" if total > 0 else ""

    parts = []
    if todo_data["completed"]:
        parts.append(f"✅ {todo_data['completed']} completed")
    if todo_data["in_progress"]:
        parts.append(f"▶️ {todo_data['in_progress']} in progress")
    if todo_data["pending"]:
        parts.append(f"☐ {todo_data['pending']} pending")
    if todo_data.get("cancelled", 0):
        parts.append(f"✗ {todo_data['cancelled']} cancelled")
    summary = "  ".join(parts)

    lines = []
    if change_description:
        lines.append(change_description)
        lines.append("")
    if total > 0:
        header = f"📋 Todo List ({done}/{total}"
        if pct:
            header += f", {pct}"
        if summary:
            header += f", {summary}"
        header += ")"
        lines.append(header)
        for todo in todo_data["todos"]:
            icon = _STATUS_ICONS.get(todo["status"], "  ")
            lines.append(f"  {icon} [{todo['id']}] {todo['content']}")
    else:
        lines.append("📋 Todo list is empty")
    lines.append(
        f'~DATA~{{"total":{total},"completed":{todo_data["completed"]},'
        f'"in_progress":{todo_data["in_progress"]},'
        f'"pending":{todo_data["pending"]}}}'
    )
    return "\n".join(lines)


def _broadcast_todo_progress(
    todo_data: dict[str, Any],
    change_description: str = "",
) -> None:
    """Push the full todo list to the active UI (if any).

    ``change_description`` is a one-liner about what just happened, shown
    above the list (e.g. ``"✅ Completed: [1] Fix login bug"``).
    """
    text = _render_todo_progress(todo_data, change_description)
    # lazy: circular — tool → ui → llm_task → here
    from zrb.llm.agent.run.runtime_state import get_current_ui

    ui = get_current_ui()
    if ui is not None:
        ui.append_to_output(text, kind="todo_progress")


# Tool functions for LLM integration


async def write_todos(
    todos: list[dict[str, Any]],
    session: str = "",
    replace: bool = True,
) -> str:
    """
    Creates or replaces the todo list for the current session.

    Each todo is a dict with keys:
      - content (str): what the task is
      - status  (str, optional): "pending", "in_progress", "completed", "cancelled" (default: "pending")
      - id      (str, optional): unique identifier (auto-assigned if omitted)

    With `replace=True` (default), all existing todos are overwritten. Pass `replace=False` to merge.
    """
    session_name = session or get_current_context_session()

    error = _validate_todo_keys(todos)
    if error:
        return error

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

    lines.append(
        "\nCall `write_todos` again with the full list to change status "
        "(it replaces by default); `get_todos` to check state."
    )

    _broadcast_todo_progress(
        result,
        change_description=f"📋 Todo list {'updated' if replace else 'merged'} ({len(todos)} items)",
    )
    return "\n".join(lines)


def _validate_todo_keys(todos: list[dict[str, Any]]) -> str | None:
    """Check every todo for unknown keys. Return an error string or None."""
    _VALID_TODO_KEYS = frozenset({"id", "content", "status"})
    _COMMON_MISTAKES: dict[str, str] = {
        "description": "content",
        "title": "content",
        "name": "content",
        "task": "content",
        "summary": "content",
        "text": "content",
    }
    for i, todo in enumerate(todos):
        unknown = set(todo) - _VALID_TODO_KEYS
        if not unknown:
            continue
        hints = []
        for bad_key in sorted(unknown):
            suggestion = _COMMON_MISTAKES.get(bad_key)
            if suggestion:
                hints.append(f"  - '{bad_key}' should be '{suggestion}'")
            else:
                hints.append(f"  - '{bad_key}' is not a recognized key")
        lines = [
            f"Error: Todo #{i + 1} contains invalid key(s):",
            *hints,
            "",
            "Each todo is a dict with these keys:",
            "  - content (str): description of the task",
            "  - status  (str): pending | in_progress | completed | cancelled",
            "  - id      (str, optional): unique identifier (auto-assigned if omitted)",
            "",
            "[SYSTEM SUGGESTION]: Use the exact keys above. Example:",
            '  write_todos(todos=[{"content": "Fix login bug", "status": "pending"},',
            '              {"content": "Add tests", "status": "pending"}])',
        ]
        return "\n".join(lines)
    return None


async def get_todos(session: str = "") -> str:
    """
    Returns the current todo list and progress summary.
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


# Export tool functions with proper names for LLM
write_todos.__name__ = "TodoWrite"
get_todos.__name__ = "TodoRead"


def create_plan_tools() -> list:
    """Create planning tools for registration with the LLM agent.

    Only TodoWrite (replace-by-default) and TodoRead are exposed: TodoWrite
    subsumes per-item status changes and clearing.
    """
    return [write_todos, get_todos]
