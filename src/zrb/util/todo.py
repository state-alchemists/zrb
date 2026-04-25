"""todo.txt task management — re-exports from split modules.

Originally a 585-line monolith, now decomposed into three focused modules:
  - todo_duration: duration string parsing and formatting
  - todo_parser:   todo.txt format parsing, serialization, selection
  - todo_render:   visual rendering (tabular lists, task cards)

All public and private symbols are re-exported here for backward compatibility.
"""

from zrb.util.file import read_file, write_file  # noqa: F401 — tests patch at this path
from zrb.util.todo_duration import (  # noqa: F401
    add_duration,
    format_duration,
    parse_duration,
)
from zrb.util.todo_parser import (  # noqa: F401
    _parse_date,
    cascade_todo_task,
    line_to_todo_task,
    load_todo_list,
    save_todo_list,
    select_todo_task,
    todo_task_to_line,
)
from zrb.util.todo_render import (  # noqa: F401
    GAP_WIDTH,
    MAX_DESCRIPTION_WIDTH,
    _get_minimum_width,
    date_to_str,
    get_line_str,
    get_visual_todo_card,
    get_visual_todo_header,
    get_visual_todo_line,
    get_visual_todo_list,
)
