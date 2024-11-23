import datetime
import re

from pydantic import BaseModel, Field


class TodoTask(BaseModel):
    priority: str | None = Field("D", regex=r"^[A-Z]$")  # Priority like A, B, ...
    status: bool = False  # True if completed, False otherwise
    description: str  # Main task description
    projects: list[str] = []  # List of projects (e.g., +Project)
    contexts: list[str] = []  # List of contexts (e.g., @Context)
    creation_date: datetime.date | None = None  # Creation date
    completion_date: datetime.date | None = None  # Completion date


# Regular expression for parsing a todo.txt line
TODO_TXT_PATTERN = re.compile(
    r"^(?:(x)\s+)?"  # Optional completion mark ('x')
    r"(?:\((?P<priority>[A-Z])\)\s+)?"  # Optional priority (e.g., '(A)')
    r"(?:(?P<completion_date>\d{4}-\d{2}-\d{2})\s+)?"  # Optional completion date
    r"(?:(?P<creation_date>\d{4}-\d{2}-\d{2})\s+)?"  # Optional creation date
    r"(?P<description>.*?)"  # Task description
    r"(?:\s+\+(?P<projects>[^\s+]+))*"  # Projects (e.g., +ProjectName)
    r"(?:\s+@(?P<contexts>[^\s@]+))*"  # Contexts (e.g., @ContextName)
    r"$"
)


def parse_todo_line(line: str) -> TodoTask:
    """Parses a single todo.txt line into a TodoTask model."""
    match = TODO_TXT_PATTERN.match(line)
    if not match:
        raise ValueError(f"Invalid todo.txt line: {line}")

    groups = match.groupdict()
    return TodoTask(
        priority=groups["priority"],
        status=bool(groups[1]),  # 'x' indicates completion
        description=groups["description"],
        projects=re.findall(
            r"\+(\S+)", groups["description"] or ""
        ),  # Extract projects
        contexts=re.findall(r"@(\S+)", groups["description"] or ""),  # Extract contexts
        creation_date=parse_date(groups["creation_date"]),
        completion_date=parse_date(groups["completion_date"]),
    )


def parse_date(date_str: str | None) -> datetime.date:
    """Parses a date string in the format YYYY-MM-DD."""
    if date_str:
        return datetime.date.fromisoformat(date_str)
    return None
