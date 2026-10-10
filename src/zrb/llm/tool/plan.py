"""Per-session todo tools (TodoWrite/TodoRead), persisted at
``~/.zrb/todos/{session_name}.json``."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field

from zrb.context.any_context import zrb_print
from zrb.llm.agent_state import get_current_ui
from zrb.llm.ambient_state import get_current_tool_session
from zrb.util.string.conversion import to_safe_filename


class TodoManager:
    """Singleton holding each session's todo list, persisted to disk."""

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

    @property
    def todo_dir(self) -> Path:
        """Directory todo files are persisted under."""
        return self._todo_dir

    @todo_dir.setter
    def todo_dir(self, value: Path) -> None:
        self._todo_dir = value

    @property
    def todos(self) -> dict[str, dict[str, Any]]:
        """The in-memory per-session todo cache."""
        return self._todos

    @todos.setter
    def todos(self, value: dict[str, dict[str, Any]]) -> None:
        self._todos = value

    def write_todos(
        self,
        session_name: str,
        todos: list[dict[str, Any]],
        replace: bool = True,
    ) -> dict[str, Any]:
        """Write todos for a session and return the list with metadata."""
        now = datetime.now().isoformat()

        existing = self.get_todos(session_name) if not replace else None
        existing_todos = (
            {t["id"]: t for t in existing.get("todos", [])} if existing else {}
        )

        new_todos = []
        used_ids: set[str] = set()
        for i, todo in enumerate(todos):
            todo_id = todo.get("id") or ""
            # Matching `existing` targets that todo for update; matching
            # `used_ids` would duplicate an id claimed earlier in this call.
            if not todo_id or todo_id in used_ids:
                todo_id = self._next_auto_id(i, existing_todos, used_ids)
            used_ids.add(todo_id)
            new_todos.append(
                self._build_todo_entry(todo, todo_id, existing_todos, replace, now)
            )

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
        self.save_todos(session_name)
        return result

    def get_todos(self, session_name: str) -> dict[str, Any] | None:
        """Get a session's todos (loading from disk if uncached), or None."""
        if session_name in self._todos:
            return self._todos[session_name]

        todo_file = self.get_todo_file(session_name)
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

    def get_todo_file(self, session_name: str) -> Path:
        """Get the file path for a session's todos."""
        return self._todo_dir / f"{to_safe_filename(session_name)}.json"

    def save_todos(self, session_name: str) -> None:
        """Save todos to disk for a session."""
        if session_name not in self._todos:
            return

        todo_file = self.get_todo_file(session_name)
        try:
            with open(todo_file, "w", encoding="utf-8") as f:
                json.dump(self._todos[session_name], f, indent=2)
        except Exception as e:
            zrb_print(
                f"Warning: Failed to save todos for {session_name}: {e}", plain=True
            )

    @staticmethod
    def _compute_stats(new_todos: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "total": len(new_todos),
            "completed": sum(1 for t in new_todos if t["status"] == "completed"),
            "in_progress": sum(1 for t in new_todos if t["status"] == "in_progress"),
            "pending": sum(1 for t in new_todos if t["status"] == "pending"),
            "cancelled": sum(1 for t in new_todos if t["status"] == "cancelled"),
        }

    @staticmethod
    def _next_auto_id(
        index: int, existing: dict[str, dict[str, Any]], used: set[str]
    ) -> str:
        """Smallest id from `index + 1` upward in neither `existing` nor `used`."""
        candidate = index + 1
        while str(candidate) in existing or str(candidate) in used:
            candidate += 1
        return str(candidate)

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


todo_manager = TodoManager()


# ── Progress visualization ─────────────────────────────────────────────────


# Plain-text status markers for the model-facing tool results.
_STATUS_CHARS = {
    "completed": "[+]",
    "in_progress": "[>]",
    "pending": "[ ]",
    "cancelled": "[-]",
}
_VALID_TODO_KEYS = frozenset({"id", "content", "status"})
_COMMON_MISTAKES: dict[str, str] = {
    "description": "content",
    "title": "content",
    "name": "content",
    "task": "content",
    "summary": "content",
    "text": "content",
}

_STATUS_ICONS = {
    "completed": "✅",
    "in_progress": "🔄",
    "pending": "  ",
    "cancelled": "✗",
}


def _render_todo_progress(
    todo_data: dict[str, Any],
    change_description: str = "",
) -> str:
    """Render the todo list for the UI, ending with a ``~DATA~`` JSON line
    for the web frontend."""
    total = todo_data["total"]
    done = todo_data["completed"]
    pct = f"{int((done / total) * 100)}%" if total > 0 else ""

    parts = []
    if todo_data["completed"]:
        parts.append(f"✅ {todo_data['completed']} completed")
    if todo_data["in_progress"]:
        parts.append(f"🔄 {todo_data['in_progress']} in progress")
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
    """Push the todo list, headed by ``change_description``, to the active UI."""
    text = _render_todo_progress(todo_data, change_description)
    ui = get_current_ui()
    if ui is not None:
        # Leading "\n  " matches other mid-turn status lines (`web.py::_notify`).
        ui.append_to_output(f"\n  {text}", kind="todo_progress")


async def write_todos(
    todos: Annotated[
        list[dict[str, Any]],
        Field(
            description=(
                'Each item: {content (str), status ("pending"|"in_progress"|'
                '"completed"|"cancelled", default "pending"), id (auto-assigned '
                "if omitted)}."
            )
        ),
    ],
    session: Annotated[
        str,
        Field(
            description="Session to write todos for; defaults to the current tool session."
        ),
    ] = "",
    replace: Annotated[
        bool,
        Field(
            description=(
                "True (default) overwrites the whole list; False merges with "
                "the existing list."
            )
        ),
    ] = True,
) -> str:
    """
    Creates or replaces the session todo list.
    To advance status, call again with the full list (replace=True).

    Mark an item `completed` only once its work is done *and* verified — the
    test run, the read-back, the grep. Never on intent, and never because the
    edit that should accomplish it has landed. An item whose verification is
    still outstanding stays `in_progress`; one that is blocked stays
    `in_progress` and gains a follow-up item naming the blocker.
    """
    session_name = session or get_current_tool_session()

    error = _validate_todo_keys(todos)
    if error:
        return error

    result = todo_manager.write_todos(session_name, todos, replace)
    lines = [
        f"[{session_name}] {result['completed']}/{result['total']} done, {result['in_progress']} in progress"
    ]
    for todo in result["todos"]:
        status_char = _STATUS_CHARS.get(todo["status"], "[?]")
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
    """Return an error string if any todo has an unknown key, else None."""
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


async def get_todos(
    session: Annotated[
        str,
        Field(
            description="Session to read todos for; defaults to the current tool session."
        ),
    ] = "",
) -> str:
    """
    Returns the current todo list and progress summary.
    """
    session_name = session or get_current_tool_session()

    result = todo_manager.get_todos(session_name)

    if not result or not result.get("todos"):
        return f"No todos for session '{session_name}'. Use `write_todos` to create a plan."

    lines = [
        f"[{session_name}] Progress: {result['completed']}/{result['total']} done, {result['in_progress']} in progress, {result['pending']} pending"
    ]
    lines.append(
        f"Updated: {result.get('updated_at', result.get('created_at', 'N/A'))}"
    )
    for todo in result["todos"]:
        status_char = _STATUS_CHARS.get(todo["status"], "[?]")
        lines.append(
            f"  {status_char} [{todo['id']}] {todo['content']} -> {todo['status']}"
        )

    if result["total"] > 0:
        progress = (result["completed"] / result["total"]) * 100
        lines.append(f"\nProgress: {progress:.0f}%")

    return "\n".join(lines)


write_todos.__name__ = "TodoWrite"
get_todos.__name__ = "TodoRead"


def create_plan_tools() -> list:
    """Return the planning tools (TodoWrite subsumes status changes and clearing)."""
    return [write_todos, get_todos]
