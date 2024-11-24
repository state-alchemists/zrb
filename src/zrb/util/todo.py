import datetime
import re

from pydantic import BaseModel, Field, model_validator


class TodoTask(BaseModel):
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


def parse_todo_line(line: str) -> TodoTask:
    """Parses a single todo.txt line into a TodoTask model."""
    match = TODO_TXT_PATTERN.match(line)
    if not match:
        raise ValueError(f"Invalid todo.txt line: {line}")
    groups = match.groupdict()
    # Extract completion status
    is_completed = groups["status"] == "x"
    # Extract dates
    date1 = parse_date(groups["date1"])
    date2 = parse_date(groups["date2"])
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
        print(keyval_str)
        key, val = keyval_str.split(":")
        keyval[key] = val
    description = re.sub(r"\s*\+\S+|\s*@\S+|\s*\S+:\S+", "", raw_description).strip()
    return TodoTask(
        priority=groups["priority"],
        completed=is_completed,
        description=description,
        projects=projects,
        contexts=contexts,
        keyval=keyval,
        creation_date=creation_date,
        completion_date=completion_date,
    )


def parse_date(date_str: str | None) -> datetime.date | None:
    """Parses a date string in the format YYYY-MM-DD."""
    if date_str:
        return datetime.date.fromisoformat(date_str)
    return None


def todo_task_to_line(task: TodoTask) -> str:
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
    # Join all parts with a space
    return " ".join(parts)
