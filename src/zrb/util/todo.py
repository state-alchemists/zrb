"""todo.txt task management — re-exports from split modules.

Originally a 585-line monolith, now decomposed into three focused modules:
  - todo_duration: duration string parsing and formatting
  - todo_parser:   todo.txt format parsing, serialization, selection
  - todo_render:   visual rendering (tabular lists, task cards)
"""

from zrb.util.todo_duration import add_duration, format_duration, parse_duration
from zrb.util.todo_parser import (
    cascade_todo_task,
    line_to_todo_task,
    load_todo_list,
    save_todo_list,
    select_todo_task,
    todo_task_to_line,
)
from zrb.util.todo_render import (
    GAP_WIDTH,
    MAX_DESCRIPTION_WIDTH,
    date_to_str,
    get_line_str,
    get_visual_todo_card,
    get_visual_todo_header,
    get_visual_todo_line,
    get_visual_todo_list,
)

__all__ = [
    "add_duration",
    "cascade_todo_task",
    "date_to_str",
    "format_duration",
    "GAP_WIDTH",
    "get_line_str",
    "get_visual_todo_card",
    "get_visual_todo_header",
    "get_visual_todo_line",
    "get_visual_todo_list",
    "line_to_todo_task",
    "load_todo_list",
    "MAX_DESCRIPTION_WIDTH",
    "parse_duration",
    "save_todo_list",
    "select_todo_task",
    "todo_task_to_line",
]
