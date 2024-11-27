import datetime
import os

from zrb.builtin.group import todo_group
from zrb.config import TODO_DIR
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.input.text_input import TextInput
from zrb.task.make_task import make_task
from zrb.util.todo import (
    TodoTaskModel,
    cascade_todo_task,
    get_visual_todo_list,
    line_to_todo_task,
    load_todo_list,
    save_todo_list,
    todo_task_to_line,
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
    todo_tasks: list[TodoTaskModel] = []
    if os.path.isfile(todo_file_path):
        todo_tasks = load_todo_list(todo_file_path)
    else:
        os.makedirs(TODO_DIR, exist_ok=True)
    todo_tasks.append(
        cascade_todo_task(
            TodoTaskModel(
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
    save_todo_list(todo_file_path, todo_tasks)
    return get_visual_todo_list(todo_tasks)


@make_task(name="todo-list", description="📋 List todo", group=todo_group, alias="list")
def todo_list(ctx: AnyContext):
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    todo_tasks: list[TodoTaskModel] = []
    if os.path.isfile(todo_file_path):
        todo_tasks = load_todo_list(todo_file_path)
    return get_visual_todo_list(todo_tasks)


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
    description="📝 Edit todo",
    group=todo_group,
    alias="edit",
)
def todo_edit(ctx: AnyContext):
    todo_tasks = [
        cascade_todo_task(line_to_todo_task(line))
        for line in ctx.input.text.split("\n")
        if line.strip() != ""
    ]
    new_content = "\n".join(todo_task_to_line(todo_task) for todo_task in todo_tasks)
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    with open(todo_file_path, "w") as f:
        f.write(new_content)
    todo_tasks = load_todo_list(todo_file_path)
    return get_visual_todo_list(todo_tasks)


def _get_todo_txt_content() -> str:
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    if not os.path.isfile(todo_file_path):
        return ""
    with open(todo_file_path, "r") as f:
        return f.read()
