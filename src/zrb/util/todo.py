import datetime
import re
import shutil
from typing import Any

from pydantic import BaseModel, Field, model_validator

from zrb.util.cli.style import (
    stylize_bold_green,
    stylize_bold_yellow,
    stylize_cyan,
    stylize_faint,
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

    def get_additional_info_length(self):
        results = []
        for project in self.projects:
            results.append(f"@{project}")
        for context in self.contexts:
            results.append(f"+{context}")
        for key, val in self.keyval.items():
            results.append(f"{key}:{val}")
        return len(", ".join(results))


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
        todo_task = line_to_todo_task(todo_line)
        todo_list.append(todo_task)
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


def get_visual_todo_list(todo_list: list[TodoTaskModel], filter: str) -> str:
    todo_filter = line_to_todo_task(filter)
    filtered_todo_list = []
    for todo_task in todo_list:
        filter_description = todo_filter.description.lower().strip()
        if (
            filter_description != ""
            and filter_description not in todo_task.description.lower()
        ):
            continue
        if not all(context in todo_task.contexts for context in todo_filter.contexts):
            continue
        if not all(project in todo_task.projects for project in todo_filter.projects):
            continue
        if not all(
            key in todo_task.keyval and todo_task.keyval[key] == val
            for key, val in todo_filter.keyval.items()
        ):
            continue
        filtered_todo_list.append(todo_task)
    if len(filtered_todo_list) == 0:
        return "\n".join(["", "  Empty todo list... 🌵🦖", ""])
    max_desc_length = max(
        len(todo_task.description) for todo_task in filtered_todo_list
    )
    if max_desc_length < len("DESCRIPTION"):
        max_desc_length = len("DESCRIPTION")
    if max_desc_length > 70:
        max_desc_length = 70
    max_additional_info_length = max(
        todo_task.get_additional_info_length() for todo_task in filtered_todo_list
    )
    if max_additional_info_length < len("PROJECT/CONTEXT/OTHERS"):
        max_additional_info_length = len("PROJECT/CONTEXT/OTHERS")
    terminal_width, _ = shutil.get_terminal_size()
    # Headers
    results = [
        stylize_faint(
            get_visual_todo_header(
                terminal_width, max_desc_length, max_additional_info_length
            )
        )
    ]
    for todo_task in filtered_todo_list:
        results.append(
            get_visual_todo_line(
                terminal_width, max_desc_length, max_additional_info_length, todo_task
            )
        )
    return "\n".join(results)


def get_visual_todo_header(
    terminal_width: int, max_desc_length: int, max_additional_info_length: int
) -> str:
    priority = "".ljust(3)
    completed = "".ljust(3)
    completed_at = "COMPLETED AT".rjust(14)
    created_at = "CREATED_AT".ljust(14)
    description = "DESCRIPTION".ljust(min(max_desc_length, 70))
    additional_info = "PROJECT/CONTEXT/OTHERS"
    if terminal_width <= 14 + max_desc_length + max_additional_info_length:
        return "  ".join([priority, completed, description])
    if terminal_width <= 36 + max_desc_length + max_additional_info_length:
        return "  ".join([priority, completed, description, additional_info])
    return "  ".join(
        [priority, completed, completed_at, created_at, description, additional_info]
    )


def get_visual_todo_line(
    terminal_width: int,
    max_desc_length: int,
    max_additional_info_length: int,
    todo_task: TodoTaskModel,
) -> str:
    completed = "[x]" if todo_task.completed else "[ ]"
    priority = "   " if todo_task.priority is None else f"({todo_task.priority})"
    completed_at = stylize_yellow(_date_to_str(todo_task.completion_date))
    created_at = stylize_cyan(_date_to_str(todo_task.creation_date))
    description = todo_task.description
    if len(description) > max_desc_length:
        description = description[: max_desc_length - 4] + " ..."
    description = description.ljust(max_desc_length)
    description = description[:max_desc_length]
    if todo_task.completed:
        description = stylize_faint(description)
    elif "duration" in todo_task.keyval:
        description = stylize_bold_yellow(description)
    additional_info = ", ".join(
        [stylize_yellow(f"+{project}") for project in todo_task.projects]
        + [stylize_cyan(f"@{context}") for context in todo_task.contexts]
        + [stylize_magenta(f"{key}:{val}") for key, val in todo_task.keyval.items()]
    )
    if terminal_width <= 14 + max_desc_length + max_additional_info_length:
        return "  ".join([priority, completed, description])
    if terminal_width <= 36 + max_desc_length + max_additional_info_length:
        return "  ".join([priority, completed, description, additional_info])
    return "  ".join(
        [priority, completed, completed_at, created_at, description, additional_info]
    )


def get_visual_todo_card(
    todo_task: TodoTaskModel, log_work_list: list[dict[str, str]]
) -> str:
    description = todo_task.description
    status = "TODO"
    if todo_task.completed:
        status = "DONE"
    elif "duration" in todo_task.keyval:
        status = "DOING"
    priority = todo_task.priority
    completed_at = (
        _date_to_str(todo_task.completion_date)
        if todo_task.completion_date is not None
        else ""
    )
    created_at = (
        _date_to_str(todo_task.creation_date)
        if todo_task.creation_date is not None
        else ""
    )
    log_work_str = "\n".join(
        [
            "  ".join(
                [
                    stylize_magenta(log_work.get("duration", "").strip().rjust(12)),
                    stylize_cyan(log_work.get("start", "").strip().rjust(20)),
                    log_work.get("log", "").strip(),
                ]
            )
            for log_work in log_work_list
        ]
    )
    detail = [
        f"{'📄 Description'.ljust(16)}: {description}",
        f"{'🎯 Priority'.ljust(16)}: {priority}",
        f"{'📊 Status'.ljust(16)}: {status}",
        f"{'📅 Created at'.ljust(16)}: {created_at}",
        f"{'✅ Completed at'.ljust(16)}: {completed_at}",
    ]
    if log_work_str != "":
        detail.append(
            stylize_faint("  ".join(["Time Spent".rjust(12), "Start".rjust(20), "Log"]))
        )
        detail.append(log_work_str)
    return "\n".join(detail)


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
