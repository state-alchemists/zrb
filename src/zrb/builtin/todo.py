import datetime
import json
import os
from typing import Any

from zrb.builtin.group import todo_group
from zrb.config import TODO_DIR
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.input.text_input import TextInput
from zrb.task.make_task import make_task
from zrb.util.todo import (
    TodoTaskModel,
    add_durations,
    cascade_todo_task,
    get_visual_todo_list,
    line_to_todo_task,
    load_todo_list,
    save_todo_list,
    select_todo_task,
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
    todo_list: list[TodoTaskModel] = []
    if os.path.isfile(todo_file_path):
        todo_list = load_todo_list(todo_file_path)
    else:
        os.makedirs(TODO_DIR, exist_ok=True)
    todo_list.append(
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
    save_todo_list(todo_file_path, todo_list)
    return get_visual_todo_list(todo_list)


@make_task(name="todo-list", description="📋 List todo", group=todo_group, alias="list")
def todo_list(ctx: AnyContext):
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    todo_tasks: list[TodoTaskModel] = []
    if os.path.isfile(todo_file_path):
        todo_tasks = load_todo_list(todo_file_path)
    return get_visual_todo_list(todo_tasks)


@make_task(
    name="todo-complete",
    input=StrInput(name="keyword", prompt="Task keyword", description="Task Keyword"),
    description="✅ Complete todo",
    group=todo_group,
    alias="complete",
)
def todo_complete(ctx: AnyContext):
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    todo_list: list[TodoTaskModel] = []
    if os.path.isfile(todo_file_path):
        todo_list = load_todo_list(todo_file_path)
    # Get todo task
    todo_task = select_todo_task(todo_list, ctx.input.keyword)
    if todo_task is None:
        ctx.log_error("Task not found")
        return get_visual_todo_list(todo_list)
    # Update todo task
    todo_task = cascade_todo_task(todo_task)
    if todo_task.creation_date is not None:
        todo_task.completion_date = datetime.date.today()
    todo_task.completed = True
    # Save todo list
    save_todo_list(todo_file_path, todo_list)
    return get_visual_todo_list(todo_list)


@make_task(
    name="todo-log",
    input=[
        StrInput(name="keyword", prompt="Task keyword", description="Task Keyword"),
        StrInput(
            name="start",
            prompt="Working start time (%Y-%m-%d %H:%M:%S)",
            description="Working start time",
            default_str=lambda _: _get_default_start(),
        ),
        StrInput(
            name="duration",
            prompt="Working duration",
            description="Working duration",
            default_str="30m",
        ),
        StrInput(
            name="log",
            prompt="Working log",
            description="Working log",
        ),
    ],
    description="🕒 Log work todo",
    group=todo_group,
    alias="log",
)
def todo_log(ctx: AnyContext):
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    todo_list: list[TodoTaskModel] = []
    if os.path.isfile(todo_file_path):
        todo_list = load_todo_list(todo_file_path)
    # Get todo task
    todo_task = select_todo_task(todo_list, ctx.input.keyword)
    if todo_task is None:
        ctx.log_error("Task not found")
        return get_visual_todo_list(todo_list)
    # Update todo task
    todo_task = cascade_todo_task(todo_task)
    current_duration = todo_task.keyval.get("duration", "0")
    todo_task.keyval["duration"] = add_durations(current_duration, ctx.input.duration)
    print(current_duration, todo_task.keyval)
    # Save todo list
    save_todo_list(todo_file_path, todo_list)
    # Add log work
    log_work_dir = os.path.join(TODO_DIR, "log-work")
    os.makedirs(log_work_dir, exist_ok=True)
    log_work_file_path = os.path.join(
        log_work_dir, f"{todo_task.keyval.get('id')}.json"
    )
    if os.path.isfile(log_work_file_path):
        with open(log_work_file_path, "r") as f:
            log_work_json = f.read()
    else:
        log_work_json = "[]"
    log_work: list[dict[str, Any]] = json.loads(log_work_json)
    log_work.append(
        {"log": ctx.input.log, "duration": ctx.input.duration, "start": ctx.input.start}
    )
    with open(log_work_file_path, "w") as f:
        f.write(json.dumps(log_work, indent=2))
    return get_visual_todo_list(todo_list)


def _get_default_start() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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
    todo_list = [
        cascade_todo_task(line_to_todo_task(line))
        for line in ctx.input.text.split("\n")
        if line.strip() != ""
    ]
    new_content = "\n".join(todo_task_to_line(todo_task) for todo_task in todo_list)
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    with open(todo_file_path, "w") as f:
        f.write(new_content)
    todo_list = load_todo_list(todo_file_path)
    return get_visual_todo_list(todo_list)


def _get_todo_txt_content() -> str:
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    if not os.path.isfile(todo_file_path):
        return ""
    with open(todo_file_path, "r") as f:
        return f.read()
