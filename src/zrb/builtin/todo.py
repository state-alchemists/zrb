import datetime
import os

from zrb.builtin.group import todo_group
from zrb.config import TODO_DIR
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.input.text_input import TextInput
from zrb.task.make_task import make_task
from zrb.util.cli.style import (
    stylize_bold_green,
    stylize_cyan,
    stylize_magenta,
    stylize_yellow,
)
from zrb.util.string.name import get_random_name
from zrb.util.todo import (
    TodoTask,
    parse_todo_line,
    read_todo_from_file,
    todo_task_to_line,
    write_todo_to_file,
)


@make_task(
    name="todo-add",
    input=[
        StrInput(
            name="description",
            description="Task description",
            prompt="Task description",
        ),
        StrInput(
            name="priority",
            description="Task priority",
            prompt="Task priority",
            default_str="E",
        ),
        StrInput(
            name="project",
            description="Task project",
            prompt="Task project (space separated)",
        ),
        StrInput(
            name="context",
            description="Task context",
            prompt="Task context (space separated)",
        ),
    ],
    description="➕ Add todo",
    group=todo_group,
    alias="add",
)
def todo_add(ctx: AnyContext):
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    todo_tasks: list[TodoTask] = []
    if os.path.isfile(todo_file_path):
        todo_tasks = read_todo_from_file(todo_file_path)
    else:
        os.makedirs(TODO_DIR, exist_ok=True)
    todo_tasks.append(
        _complete_todo_task(
            TodoTask(
                priority=ctx.input.priority.upper(),
                description=ctx.input.description,
                contexts=[
                    context.strip()
                    for context in ctx.input.context.split(" ")
                    if context.strip() != ""
                ],
                projects=[
                    project.strip()
                    for project in ctx.input.project.split(" ")
                    if project.strip() != ""
                ],
            )
        )
    )
    write_todo_to_file(todo_file_path, todo_tasks)
    return _get_visual_todo_list()


@make_task(name="todo-list", description="📋 List todo", group=todo_group, alias="list")
def todo_list(ctx: AnyContext):
    return _get_visual_todo_list()


@make_task(
    name="todo-edit",
    input=[
        TextInput(
            name="text",
            description="Todo.txt content",
            prompt="Todo.txt content (will override existing)",
            default_str=lambda _: _get_todo_txt_content(),
        ),
    ],
    description="✏️ Edit todo",
    group=todo_group,
    alias="edit",
)
def todo_edit(ctx: AnyContext):
    todo_tasks = [
        _complete_todo_task(parse_todo_line(line))
        for line in ctx.input.text.split("\n")
        if line.strip() != ""
    ]
    new_content = "\n".join(todo_task_to_line(todo_task) for todo_task in todo_tasks)
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    with open(todo_file_path, "w") as f:
        f.write(new_content)
    return _get_visual_todo_list()


def _complete_todo_task(todo_task: TodoTask):
    if todo_task.creation_date is None:
        todo_task.creation_date = datetime.date.today()
    if "id" not in todo_task.keyval:
        todo_task.keyval["id"] = get_random_name()
    return todo_task


def _get_visual_todo_list() -> str:
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    if not os.path.isfile(todo_file_path):
        return "\n".join(["", "  Todo.txt not found... 🌵🦖", ""])
    todo_tasks = read_todo_from_file(todo_file_path)
    if len(todo_tasks) == 0:
        return "\n".join(["", "  Empty todo list... 🌵🦖", ""])
    max_desc_name_length = max(len(todo_task.description) for todo_task in todo_tasks)
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
    for todo_task in todo_tasks:
        completed = "[x]" if todo_task.completed else "[ ]"
        priority = "   " if todo_task.priority is None else f"({todo_task.priority})"
        completion_date = stylize_yellow(_date_to_str(todo_task.completion_date))
        creation_date = stylize_cyan(_date_to_str(todo_task.creation_date))
        description = todo_task.description.ljust(max_desc_name_length)
        additions = ", ".join(
            [stylize_yellow(f"@{project}") for project in todo_task.projects]
            + [stylize_cyan(f"+{context}") for context in todo_task.contexts]
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


def _get_todo_txt_content() -> str:
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    if not os.path.isfile(todo_file_path):
        return ""
    with open(todo_file_path, "r") as f:
        return f.read()
