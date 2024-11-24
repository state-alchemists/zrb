import datetime
import os

from zrb.builtin.group import todo_group
from zrb.config import TODO_DIR
from zrb.context.any_context import AnyContext
from zrb.task.make_task import make_task
from zrb.util.cli.style import (
    stylize_bold_green,
    stylize_cyan,
    stylize_magenta,
    stylize_yellow,
)
from zrb.util.todo import TodoTask, parse_todo_line


def _date_to_str(date: datetime.date | None) -> str:
    if date is None:
        return "".ljust(10)
    return date.strftime("%Y-%m-%d")


@make_task(name="todo-list", description="📋 List todo", group=todo_group, alias="list")
def todo_list(ctx: AnyContext):
    # txt = """
    # (A) Thank Mom for the meatballs @phone
    # (B) Schedule Goodwill pickup +GarageSale @phone
    # Post signs around the neighborhood +GarageSale
    # @GroceryStore Eskimo pies due:2024-10-13
    # x 2011-03-03 Call Mom
    # x 2011-03-02 2011-03-01 Review Tim's pull request +TodoTxtTouch @github
    # """
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    if not os.path.isfile(todo_file_path):
        ctx.log_error(f"Todo file not found: {todo_file_path}")
        return
    with open(todo_file_path, "r") as f:
        todo_lines = f.read().strip().split("\n")
    todo_tasks: list[TodoTask] = []
    for todo_line in todo_lines:
        todo_line = todo_line.strip()
        if todo_line == "":
            continue
        todo_tasks.append(parse_todo_line(todo_line))
    max_desc_name_length = max(len(todo_task.description) for todo_task in todo_tasks)
    results = [
        stylize_bold_green(
            " ".join(
                [
                    "".ljust(3),  # priority
                    "".ljust(3),  # completed
                    "Completed".ljust(10),  # completed date
                    "Created".ljust(10),  # completed date
                    "Description".ljust(max_desc_name_length),
                    "Project/Context/Other",
                ]
            )
        )
    ]
    for todo_task in todo_tasks:
        priority = "(Z)" if todo_task.priority is None else f"({todo_task.priority})"
        completed = "[x]" if todo_task.completed else "[ ]"
        creation_date = _date_to_str(todo_task.creation_date)
        completion_date = _date_to_str(todo_task.completion_date)
        description = todo_task.description.ljust(max_desc_name_length)
        additions = ", ".join(
            [stylize_yellow(f"@{project}") for project in todo_task.projects]
            + [stylize_cyan(f"+{context}") for context in todo_task.contexts]
            + [stylize_magenta(f"{key}:{val}") for key, val in todo_task.keyval.items()]
        )
        results.append(
            " ".join(
                [
                    priority,
                    completed,
                    completion_date,
                    creation_date,
                    description,
                    additions,
                ]
            )
        )
    return "\n".join(results)
