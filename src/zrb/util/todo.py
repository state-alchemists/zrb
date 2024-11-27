import datetime
import re

from pydantic import BaseModel, Field, model_validator

from zrb.util.cli.style import (
    stylize_bold_green,
    stylize_cyan,
    stylize_magenta,
    stylize_yellow,
)
from zrb.util.string.name import get_random_name


class TodoTaskModel(BaseModel):
    priority: str | None = Field("D", pattern=r"^[A-Z]$")  # Priority like A, B, ...
    completed: bool = False  # True if completed, False otherwise
    description: str  # Main task description
    projects: list[str] = []  # List of projects (e.g., +Project)
    contexts: list[str] = []  # List of contexts (e.g., @Context)
    keyval: dict[str, str] = {}  # Special key (e.g., due:2016-05-30)
    creation_date: datetime.date | None = None  # Creation date
    completion_date: datetime.date | None = None  # Completion date

    @model_validator(mode="before")
    def validate_dates(cls, values):
        completion_date = values.get("completion_date")
        creation_date = values.get("creation_date")
        if completion_date and not creation_date:
            raise ValueError(
                "creation_date must be specified if completion_date is set."
            )
        return values


TODO_TXT_PATTERN = re.compile(
    r"^(?P<status>x)?\s*"  # Optional completion mark ('x')
    r"(?:\((?P<priority>[A-Z])\)\s+)?"  # Optional priority (e.g., '(A)')
    r"(?P<date1>\d{4}-\d{2}-\d{2})?\s*"  # Optional first date
    r"(?P<date2>\d{4}-\d{2}-\d{2})?\s*"  # Optional second date
    r"(?P<description>.*?)$"  # Main description
)


def cascade_todo_task(todo_task: TodoTaskModel):
    if todo_task.creation_date is None:
        todo_task.creation_date = datetime.date.today()
    if "id" not in todo_task.keyval:
        todo_task.keyval["id"] = get_random_name()
    return todo_task


def select_todo_task(
    todo_list: list[TodoTaskModel], keyword: str
) -> TodoTaskModel | None:
    for todo_task in todo_list:
        id = todo_task.keyval.get("id", "")
        if keyword.lower().strip() == id.lower().strip():
            return todo_task
    for todo_task in todo_list:
        description = todo_task.description
        if keyword.lower().strip() == description.lower().strip():
            return todo_task
    for todo_task in todo_list:
        id = todo_task.keyval.get("id", "")
        if keyword.lower().strip() in id.lower().strip():
            return todo_task
    for todo_task in todo_list:
        description = todo_task.description
        if keyword.lower().strip() in description.lower().strip():
            return todo_task
    return None


def load_todo_list(todo_file_path: str) -> list[TodoTaskModel]:
    with open(todo_file_path, "r") as f:
        todo_lines = f.read().strip().split("\n")
    todo_list: list[TodoTaskModel] = []
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


def save_todo_list(todo_file_path: str, todo_list: list[TodoTaskModel]):
    with open(todo_file_path, "w") as f:
        for todo_task in todo_list:
            f.write(todo_task_to_line(todo_task) + "\n")


def line_to_todo_task(line: str) -> TodoTaskModel:
    """Parses a single todo.txt line into a TodoTask model."""
    match = TODO_TXT_PATTERN.match(line)
    if not match:
        raise ValueError(f"Invalid todo.txt line: {line}")
    groups = match.groupdict()
    # Extract completion status
    is_completed = groups["status"] == "x"
    # Extract dates
    date1 = _parse_date(groups["date1"])
    date2 = _parse_date(groups["date2"])
    # Determine creation_date and completion_date
    completion_date, creation_date = None, None
    if date2 is None:
        creation_date = date1
    else:
        completion_date = date1
        creation_date = date2
    # Extract and clean description
    raw_description = groups["description"] or ""
    projects = re.findall(r"\+(\S+)", raw_description)
    contexts = re.findall(r"@(\S+)", raw_description)
    keyval = {}
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
    """Parses a date string in the format YYYY-MM-DD."""
    if date_str:
        return datetime.date.fromisoformat(date_str)
    return None


def todo_task_to_line(task: TodoTaskModel) -> str:
    """Converts a TodoTask instance back into a todo.txt formatted line."""
    parts = []
    # Add completion mark if task is completed
    if task.completed:
        parts.append("x")
    # Add priority if present
    if task.priority:
        parts.append(f"({task.priority})")
    # Add completion and creation dates if present
    if task.completion_date:
        parts.append(task.completion_date.isoformat())
    if task.creation_date:
        parts.append(task.creation_date.isoformat())
    # Add description
    parts.append(task.description)
    # Append projects
    for project in task.projects:
        parts.append(f"+{project}")
    # Append contexts
    for context in task.contexts:
        parts.append(f"@{context}")
    # Append keyval
    for key, val in task.keyval.items():
        parts.append(f"{key}:{val}")
    # Join all parts with a space
    return " ".join(parts)


def get_visual_todo_list(todo_list: list[TodoTaskModel]) -> str:
    if len(todo_list) == 0:
        return "\n".join(["", "  Empty todo list... 🌵🦖", ""])
    max_desc_name_length = max(len(todo_task.description) for todo_task in todo_list)
    if max_desc_name_length < len("DESCRIPTION"):
        max_desc_name_length = len("DESCRIPTION")
    # Headers
    results = [
        stylize_bold_green(
            "  ".join(
                [
                    "".ljust(3),  # priority
                    "".ljust(3),  # completed
                    "COMPLETED AT".rjust(14),  # completed date
                    "CREATED AT".rjust(14),  # completed date
                    "DESCRIPTION".ljust(max_desc_name_length),
                    "PROJECT/CONTEXT/OTHERS",
                ]
            )
        )
    ]
    for todo_task in todo_list:
        completed = "[x]" if todo_task.completed else "[ ]"
        priority = "   " if todo_task.priority is None else f"({todo_task.priority})"
        completion_date = stylize_yellow(_date_to_str(todo_task.completion_date))
        creation_date = stylize_cyan(_date_to_str(todo_task.creation_date))
        description = todo_task.description.ljust(max_desc_name_length)
        additions = ", ".join(
            [stylize_yellow(f"+{project}") for project in todo_task.projects]
            + [stylize_cyan(f"@{context}") for context in todo_task.contexts]
            + [stylize_magenta(f"{key}:{val}") for key, val in todo_task.keyval.items()]
        )
        results.append(
            "  ".join(
                [
                    completed,
                    priority,
                    completion_date,
                    creation_date,
                    description,
                    additions,
                ]
            )
        )
    return "\n".join(results)


def _date_to_str(date: datetime.date | None) -> str:
    if date is None:
        return "".ljust(14)
    return date.strftime("%a %Y-%m-%d")


def add_durations(duration1: str, duration2: str) -> str:
    total_seconds = _parse_duration(duration1) + _parse_duration(duration2)
    # Format and return the result
    return _format_duration(total_seconds)


def _parse_duration(duration: str) -> int:
    """Parse a duration string into total seconds."""
    units = {"M": 2592000, "w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
    total_seconds = 0
    match = re.findall(r"(\d+)([Mwdhms])", duration)
    for value, unit in match:
        total_seconds += int(value) * units[unit]
    return total_seconds


def _format_duration(total_seconds: int) -> str:
    """Format total seconds into a duration string."""
    units = [
        ("w", 604800),  # 7 days in a week
        ("d", 86400),  # 24 hours in a day
        ("h", 3600),  # 60 minutes in an hour
        ("m", 60),  # 60 seconds in a minute
        ("s", 1),  # seconds
    ]
    result = []
    for unit, value_in_seconds in units:
        if total_seconds >= value_in_seconds:
            amount, total_seconds = divmod(total_seconds, value_in_seconds)
            result.append(f"{amount}{unit}")
    return "".join(result) if result else "0s"
