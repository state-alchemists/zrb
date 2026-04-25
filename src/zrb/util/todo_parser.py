"""todo.txt format: parsing, serialization, and TodoTaskModel selection."""

from __future__ import annotations

import datetime
import re
from typing import TYPE_CHECKING

from zrb.util.file import read_file, write_file
from zrb.util.string.name import get_random_name

if TYPE_CHECKING:
    from zrb.util.todo_model import TodoTaskModel


TODO_TXT_PATTERN = re.compile(
    r"^(?P<status>x)?\s*"  # Optional completion mark ('x')
    r"(?:\((?P<priority>[A-Z])\)\s+)?"  # Optional priority (e.g., '(A)')
    r"(?P<date1>\d{4}-\d{2}-\d{2})?\s*"  # Optional first date
    r"(?P<date2>\d{4}-\d{2}-\d{2})?\s*"  # Optional second date
    r"(?P<description>.*?)$"  # Main description
)


def cascade_todo_task(todo_task: "TodoTaskModel"):
    """Populate default `creation_date` and `keyval['id']` if missing."""
    if todo_task.creation_date is None:
        todo_task.creation_date = datetime.date.today()
    if "id" not in todo_task.keyval:
        todo_task.keyval["id"] = get_random_name()
    return todo_task


def select_todo_task(
    todo_list: list["TodoTaskModel"], keyword: str
) -> "TodoTaskModel | None":
    """Pick a todo task by ID or description: exact match first, then partial."""
    k = keyword.lower().strip()
    for todo_task in todo_list:
        if k == todo_task.keyval.get("id", "").lower().strip():
            return todo_task
    for todo_task in todo_list:
        if k == todo_task.description.lower().strip():
            return todo_task
    for todo_task in todo_list:
        if k in todo_task.keyval.get("id", "").lower().strip():
            return todo_task
    for todo_task in todo_list:
        if k in todo_task.description.lower().strip():
            return todo_task
    return None


def load_todo_list(todo_file_path: str) -> list["TodoTaskModel"]:
    """Load and sort todo tasks from a todo.txt file."""
    todo_lines = read_file(todo_file_path).strip().split("\n")
    todo_list: list["TodoTaskModel"] = []
    for todo_line in todo_lines:
        todo_line = todo_line.strip()
        if todo_line == "":
            continue
        todo_list.append(line_to_todo_task(todo_line))
    todo_list.sort(
        key=lambda task: (
            task.completed,
            task.priority if task.priority else "Z",
            task.projects[0] if task.projects else "zzz",
            task.creation_date if task.creation_date else datetime.date.max,
        )
    )
    return todo_list


def save_todo_list(todo_file_path: str, todo_list: list["TodoTaskModel"]):
    """Serialize and write `todo_list` to `todo_file_path`."""
    write_file(
        todo_file_path, [todo_task_to_line(todo_task) for todo_task in todo_list]
    )


def line_to_todo_task(line: str) -> "TodoTaskModel":
    """Parse a single todo.txt line into a `TodoTaskModel`."""
    from zrb.util.todo_model import TodoTaskModel

    match = TODO_TXT_PATTERN.match(line)
    if not match:
        raise ValueError(f"Invalid todo.txt line: {line}")
    groups = match.groupdict()
    is_completed = groups["status"] == "x"
    date1 = _parse_date(groups["date1"])
    date2 = _parse_date(groups["date2"])
    completion_date, creation_date = None, None
    if date2 is None:
        creation_date = date1
    else:
        completion_date = date1
        creation_date = date2

    raw_description = groups["description"] or ""
    projects = re.findall(r"\+(\S+)", raw_description)
    contexts = re.findall(r"@(\S+)", raw_description)
    keyval: dict[str, str] = {}
    for keyval_str in re.findall(r"(\S+:\S+)", raw_description):
        key, val = keyval_str.split(":", 1)
        keyval[key] = val
    description = re.sub(r"\s*\+\S+|\s*@\S+|\s*\S+:\S+", "", raw_description).strip()
    return TodoTaskModel(
        priority=groups["priority"],
        completed=is_completed,
        description=description,
        projects=projects,
        contexts=contexts,
        keyval=keyval,
        creation_date=creation_date,
        completion_date=completion_date,
    )


def _parse_date(date_str: str | None) -> datetime.date | None:
    """Parse a YYYY-MM-DD string. Returns None if `date_str` is None."""
    if date_str:
        return datetime.date.fromisoformat(date_str)
    return None


def todo_task_to_line(task: "TodoTaskModel") -> str:
    """Serialize a `TodoTaskModel` back to its todo.txt line."""
    parts = []
    if task.completed:
        parts.append("x")
    if task.priority:
        parts.append(f"({task.priority})")
    if task.completion_date:
        parts.append(task.completion_date.isoformat())
    if task.creation_date:
        parts.append(task.creation_date.isoformat())
    parts.append(task.description)
    for project in task.projects:
        parts.append(f"+{project}")
    for context in task.contexts:
        parts.append(f"@{context}")
    for key, val in task.keyval.items():
        parts.append(f"{key}:{val}")
    return " ".join(parts)
