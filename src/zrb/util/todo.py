import datetime
import re
import shutil
from typing import TYPE_CHECKING

from zrb.util.cli.style import (
    stylize_bold_yellow,
    stylize_cyan,
    stylize_faint,
    stylize_magenta,
    stylize_yellow,
)
from zrb.util.file import read_file, write_file
from zrb.util.string.name import get_random_name

if TYPE_CHECKING:
    from zrb.util.todo_model import TodoTaskModel

_DATE_TIME_STR_WIDTH = 14
_MAX_DESCRIPTION_WIDTH = 70
_PRIORITY_WIDTH = 3
_COMPLETED_WIDTH = 3
_COMPLETED_AT_WIDTH = _DATE_TIME_STR_WIDTH
_CREATED_AT_WIDTH = _DATE_TIME_STR_WIDTH
_GAP_WIDTH = 2


TODO_TXT_PATTERN = re.compile(
    r"^(?P<status>x)?\s*"  # Optional completion mark ('x')
    r"(?:\((?P<priority>[A-Z])\)\s+)?"  # Optional priority (e.g., '(A)')
    r"(?P<date1>\d{4}-\d{2}-\d{2})?\s*"  # Optional first date
    r"(?P<date2>\d{4}-\d{2}-\d{2})?\s*"  # Optional second date
    r"(?P<description>.*?)$"  # Main description
)


def cascade_todo_task(todo_task: "TodoTaskModel"):
    """
    Populate default values for a TodoTaskModel if they are missing.

    Args:
        todo_task (TodoTaskModel): The todo task model to cascade.

    Returns:
        TodoTaskModel: The todo task model with default values populated.
    """
    if todo_task.creation_date is None:
        todo_task.creation_date = datetime.date.today()
    if "id" not in todo_task.keyval:
        todo_task.keyval["id"] = get_random_name()
    return todo_task


def select_todo_task(
    todo_list: list["TodoTaskModel"], keyword: str
) -> "TodoTaskModel | None":
    """
    Select a todo task from a list based on a keyword matching ID or description.

    Args:
        todo_list (list[TodoTaskModel]): The list of todo tasks.
        keyword (str): The keyword to search for.

    Returns:
        TodoTaskModel | None: The matched todo task, or None if no match is found.
    """
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


def load_todo_list(todo_file_path: str) -> list["TodoTaskModel"]:
    """
    Load a list of todo tasks from a todo.txt file.

    Args:
        todo_file_path (str): The path to the todo.txt file.

    Returns:
        list[TodoTaskModel]: A sorted list of todo tasks.
    """
    todo_lines = read_file(todo_file_path).strip().split("\n")
    todo_list: list["TodoTaskModel"] = []
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


def save_todo_list(todo_file_path: str, todo_list: list["TodoTaskModel"]):
    """
    Save a list of todo tasks to a todo.txt file.

    Args:
        todo_file_path (str): The path to the todo.txt file.
        todo_list (list[TodoTaskModel]): The list of todo tasks to save.
    """
    write_file(
        todo_file_path, [todo_task_to_line(todo_task) for todo_task in todo_list]
    )


def line_to_todo_task(line: str) -> "TodoTaskModel":
    """Parses a single todo.txt line into a TodoTask model."""
    from zrb.util.todo_model import TodoTaskModel

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
    """
    Parses a date string in the format YYYY-MM-DD.

    Args:
        date_str (str | None): The date string to parse.

    Returns:
        datetime.date | None: The parsed date object, or None if the input is None.
    """
    if date_str:
        return datetime.date.fromisoformat(date_str)
    return None


def todo_task_to_line(task: "TodoTaskModel") -> str:
    """
    Converts a TodoTask instance back into a todo.txt formatted line.

    Args:
        task (TodoTaskModel): The todo task instance.

    Returns:
        str: The todo.txt formatted line.
    """
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


def get_visual_todo_list(todo_list: list["TodoTaskModel"], filter: str) -> str:
    """
    Generate a visual representation of a filtered todo list.

    Args:
        todo_list (list[TodoTaskModel]): The list of todo tasks.
        filter (str): The filter string in todo.txt format.

    Returns:
        str: A formatted string representing the filtered todo list.
    """
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
    if max_desc_length > _MAX_DESCRIPTION_WIDTH:
        max_desc_length = _MAX_DESCRIPTION_WIDTH
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
    """
    Generate the header string for the visual todo list.

    Args:
        terminal_width (int): The width of the terminal.
        max_desc_length (int): The maximum length of the description column.
        max_additional_info_length (int): The maximum length of the additional info column.

    Returns:
        str: The formatted header string.
    """
    priority_caption = "".ljust(_PRIORITY_WIDTH)
    completed_caption = "".ljust(_COMPLETED_WIDTH)
    completed_at_caption = "COMPLETED AT".rjust(_COMPLETED_AT_WIDTH)
    created_at_caption = "CREATED_AT".ljust(_CREATED_AT_WIDTH)
    description_caption = "DESCRIPTION".ljust(
        min(max_desc_length, _MAX_DESCRIPTION_WIDTH)
    )
    additional_info_caption = "PROJECT/CONTEXT/OTHERS".ljust(max_additional_info_length)
    return _get_line_str(
        terminal_width=terminal_width,
        description_width=min(max_desc_length, _MAX_DESCRIPTION_WIDTH),
        additional_info_width=max_additional_info_length,
        priority=priority_caption,
        completed=completed_caption,
        completed_at=completed_at_caption,
        created_at=created_at_caption,
        description=description_caption,
        additional_info=additional_info_caption,
    )


def get_visual_todo_line(
    terminal_width: int,
    max_desc_length: int,
    max_additional_info_length: int,
    todo_task: "TodoTaskModel",
) -> str:
    """
    Generate a single line string for a todo task in the visual todo list.

    Args:
        terminal_width (int): The width of the terminal.
        max_desc_length (int): The maximum length of the description column.
        max_additional_info_length (int): The maximum length of the additional info column.
        todo_task (TodoTaskModel): The todo task to format.

    Returns:
        str: The formatted line string for the todo task.
    """
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
    return _get_line_str(
        terminal_width=terminal_width,
        description_width=min(max_desc_length, _MAX_DESCRIPTION_WIDTH),
        additional_info_width=max_additional_info_length,
        priority=priority,
        completed=completed,
        completed_at=completed_at,
        created_at=created_at,
        description=description,
        additional_info=additional_info,
    )
    if terminal_width <= 14 + max_desc_length + max_additional_info_length:
        return "  ".join([priority, completed, description])
    if terminal_width <= 36 + max_desc_length + max_additional_info_length:
        return "  ".join([priority, completed, description, additional_info])
    return "  ".join(
        [priority, completed, completed_at, created_at, description, additional_info]
    )


def _get_line_str(
    terminal_width: int,
    description_width: int,
    additional_info_width: int,
    priority: str,
    completed: str,
    completed_at: str,
    created_at: str,
    description: str,
    additional_info: str,
):
    """
    Helper function to format a line string based on terminal width.

    Args:
        terminal_width (int): The width of the terminal.
        description_width (int): The width of the description column.
        additional_info_width (int): The width of the additional info column.
        priority (str): The formatted priority string.
        completed (str): The formatted completed status string.
        completed_at (str): The formatted completed at date string.
        created_at (str): The formatted created at date string.
        description (str): The formatted description string.
        additional_info (str): The formatted additional info string.

    Returns:
        str: The formatted line string.
    """
    gap = "".ljust(_GAP_WIDTH)
    if terminal_width >= _get_minimum_width(
        [
            _PRIORITY_WIDTH,
            _COMPLETED_WIDTH,
            _COMPLETED_AT_WIDTH,
            _CREATED_AT_WIDTH,
            description_width,
            additional_info_width,
        ]
    ):
        return gap.join(
            [
                priority,
                completed,
                completed_at,
                created_at,
                description,
                additional_info,
            ]
        )
    if terminal_width >= _get_minimum_width(
        [_PRIORITY_WIDTH, _COMPLETED_WIDTH, description_width, additional_info_width]
    ):
        return gap.join([priority, completed, description, additional_info])
    if terminal_width >= _get_minimum_width(
        [
            _PRIORITY_WIDTH,
            _COMPLETED_WIDTH,
            _COMPLETED_AT_WIDTH,
            _CREATED_AT_WIDTH,
            description_width,
        ]
    ):
        return gap.join([priority, completed, completed_at, created_at, description])
    if terminal_width >= _get_minimum_width(
        [_PRIORITY_WIDTH, _COMPLETED_WIDTH, description_width]
    ):
        return gap.join([priority, completed, description])
    return gap.join([priority, description])


def _get_minimum_width(field_widths: list[int]) -> int:
    """
    Helper function to calculate the minimum width required for a list of fields.

    Args:
        field_widths (list[int]): A list of widths for each field.

    Returns:
        int: The minimum total width required.
    """
    gap_width = _GAP_WIDTH * (len(field_widths) - 1)
    return sum(field_width for field_width in field_widths) + gap_width


def get_visual_todo_card(
    todo_task: "TodoTaskModel", log_work_list: list[dict[str, str]]
) -> str:
    """
    Generate a visual card representation of a todo task with log work.

    Args:
        todo_task (TodoTaskModel): The todo task to display.
        log_work_list (list[dict[str, str]]): A list of log work entries for the task.

    Returns:
        str: A formatted string representing the todo task card.
    """
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
    """
    Helper function to format a date object as a string.

    Args:
        date (datetime.date | None): The date object to format.

    Returns:
        str: The formatted date string, or an empty string if the input is None.
    """
    if date is None:
        return "".ljust(14)
    return date.strftime("%a %Y-%m-%d")


def add_duration(duration1: str, duration2: str) -> str:
    """
    Add two duration strings.

    Args:
        duration1 (str): The first duration string.
        duration2 (str): The second duration string.

    Returns:
        str: The sum of the two durations as a formatted string.
    """
    total_seconds = parse_duration(duration1) + parse_duration(duration2)
    # Format and return the result
    return _format_duration(total_seconds)


def parse_duration(duration: str) -> int:
    """
    Parse a duration string into total seconds.

    Args:
        duration (str): The duration string to parse.

    Returns:
        int: The total duration in seconds.
    """
    units = {"M": 2592000, "w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
    total_seconds = 0
    match = re.findall(r"(\d+)([Mwdhms])", duration)
    for value, unit in match:
        total_seconds += int(value) * units[unit]
    return total_seconds


def _format_duration(total_seconds: int) -> str:
    """
    Format total seconds into a duration string.

    Args:
        total_seconds (int): The total duration in seconds.

    Returns:
        str: The formatted duration string.
    """
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
