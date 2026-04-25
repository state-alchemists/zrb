"""Visual rendering for todo lists: tabular list, header row, and per-task card."""

from __future__ import annotations

import datetime
import shutil
from typing import TYPE_CHECKING

from zrb.util.cli.style import (
    stylize_bold_yellow,
    stylize_cyan,
    stylize_faint,
    stylize_magenta,
    stylize_yellow,
)
from zrb.util.todo_parser import line_to_todo_task

if TYPE_CHECKING:
    from zrb.util.todo_model import TodoTaskModel


_DATE_TIME_STR_WIDTH = 14
_MAX_DESCRIPTION_WIDTH = 70
_PRIORITY_WIDTH = 3
_COMPLETED_WIDTH = 3
_COMPLETED_AT_WIDTH = _DATE_TIME_STR_WIDTH
_CREATED_AT_WIDTH = _DATE_TIME_STR_WIDTH
_GAP_WIDTH = 2


def get_visual_todo_list(todo_list: list["TodoTaskModel"], filter: str) -> str:
    """Render `todo_list` as a tabular string, filtering by a todo.txt-format query."""
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
                terminal_width,
                max_desc_length,
                max_additional_info_length,
                todo_task,
            )
        )
    return "\n".join(results)


def get_visual_todo_header(
    terminal_width: int, max_desc_length: int, max_additional_info_length: int
) -> str:
    """Header row for the visual todo list."""
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
    """Render a single todo task as a styled line."""
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
    """Pick a column layout that fits `terminal_width` and join the parts."""
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
    """Total width needed for `field_widths` plus gaps between them."""
    gap_width = _GAP_WIDTH * (len(field_widths) - 1)
    return sum(field_width for field_width in field_widths) + gap_width


def get_visual_todo_card(
    todo_task: "TodoTaskModel", log_work_list: list[dict[str, str]]
) -> str:
    """Render a single todo task as a multi-line detail card."""
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
    """Format a date as `Mon YYYY-MM-DD`. Empty padded string for None."""
    if date is None:
        return "".ljust(14)
    return date.strftime("%a %Y-%m-%d")
