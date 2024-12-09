import datetime
import json
import os
from typing import Any

from zrb.builtin.group import todo_group
from zrb.config import TODO_DIR, TODO_VISUAL_FILTER
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.input.text_input import TextInput
from zrb.task.make_task import make_task
from zrb.util.todo import (
    TodoTaskModel,
    add_durations,
    cascade_todo_task,
    get_visual_todo_card,
    get_visual_todo_list,
    line_to_todo_task,
    load_todo_list,
    save_todo_list,
    select_todo_task,
    todo_task_to_line,
)


@make_task(
    name="add-todo",
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
            allow_empty=True,
        ),
        StrInput(
            name="context",
            description="Task context",
            prompt="Task context (space separated)",
            allow_empty=True,
        ),
    ],
    description="➕ Add todo",
    group=todo_group,
    alias="add",
)
def add_todo(ctx: AnyContext):
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
    return get_visual_todo_list(todo_list, TODO_VISUAL_FILTER)


@make_task(name="list-todo", description="📋 List todo", group=todo_group, alias="list")
def list_todo(ctx: AnyContext):
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    todo_list: list[TodoTaskModel] = []
    if os.path.isfile(todo_file_path):
        todo_list = load_todo_list(todo_file_path)
    return get_visual_todo_list(todo_list, TODO_VISUAL_FILTER)


@make_task(
    name="show-todo",
    input=StrInput(name="keyword", prompt="Task keyword", description="Task Keyword"),
    description="🔍 Show todo",
    group=todo_group,
    alias="show",
)
def show_todo(ctx: AnyContext):
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    todo_list: list[TodoTaskModel] = []
    todo_list: list[TodoTaskModel] = []
    if os.path.isfile(todo_file_path):
        todo_list = load_todo_list(todo_file_path)
    # Get todo task
    todo_task = select_todo_task(todo_list, ctx.input.keyword)
    if todo_task is None:
        ctx.log_error("Task not found")
        return
    if todo_task.completed:
        ctx.log_error("Task already completed")
        return
    # Update todo task
    todo_task = cascade_todo_task(todo_task)
    task_id = todo_task.keyval.get("id", "")
    log_work_path = os.path.join(TODO_DIR, "log-work", f"{task_id}.json")
    log_work_list = []
    if os.path.isfile(log_work_path):
        with open(log_work_path, "r") as f:
            log_work_list = json.loads(f.read())
    return get_visual_todo_card(todo_task, log_work_list)


@make_task(
    name="complete-todo",
    input=StrInput(name="keyword", prompt="Task keyword", description="Task Keyword"),
    description="✅ Complete todo",
    group=todo_group,
    alias="complete",
)
def complete_todo(ctx: AnyContext):
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    todo_list: list[TodoTaskModel] = []
    if os.path.isfile(todo_file_path):
        todo_list = load_todo_list(todo_file_path)
    # Get todo task
    todo_task = select_todo_task(todo_list, ctx.input.keyword)
    if todo_task is None:
        ctx.log_error("Task not found")
        return get_visual_todo_list(todo_list, TODO_VISUAL_FILTER)
    if todo_task.completed:
        ctx.log_error("Task already completed")
        return get_visual_todo_list(todo_list, TODO_VISUAL_FILTER)
    # Update todo task
    todo_task = cascade_todo_task(todo_task)
    if todo_task.creation_date is not None:
        todo_task.completion_date = datetime.date.today()
    todo_task.completed = True
    # Save todo list
    save_todo_list(todo_file_path, todo_list)
    return get_visual_todo_list(todo_list, TODO_VISUAL_FILTER)


@make_task(
    name="archive-todo",
    description="📚 Archive todo",
    group=todo_group,
    alias="archive",
)
def archive_todo(ctx: AnyContext):
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    todo_list: list[TodoTaskModel] = []
    if os.path.isfile(todo_file_path):
        todo_list = load_todo_list(todo_file_path)
    working_todo_list = [
        todo_task for todo_task in todo_list if not todo_task.completed
    ]
    new_archived_todo_list = [
        todo_task for todo_task in todo_list if todo_task.completed
    ]
    if len(new_archived_todo_list) == 0:
        ctx.print("No completed task to archive")
        return get_visual_todo_list(todo_list, TODO_VISUAL_FILTER)
    archive_file_path = os.path.join(TODO_DIR, "archive.txt")
    if not os.path.isdir(TODO_DIR):
        os.make_dirs(TODO_DIR, exist_ok=True)
    # Get archived todo list
    archived_todo_list = []
    if os.path.isfile(archive_file_path):
        archived_todo_list = load_todo_list(archive_file_path)
    archived_todo_list += new_archived_todo_list
    # Save the new todo list and add the archived ones
    save_todo_list(archive_file_path, archived_todo_list)
    save_todo_list(todo_file_path, working_todo_list)
    return get_visual_todo_list(todo_list, TODO_VISUAL_FILTER)


@make_task(
    name="log-todo",
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
def log_todo(ctx: AnyContext):
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    todo_list: list[TodoTaskModel] = []
    if os.path.isfile(todo_file_path):
        todo_list = load_todo_list(todo_file_path)
    # Get todo task
    todo_task = select_todo_task(todo_list, ctx.input.keyword)
    if todo_task is None:
        ctx.log_error("Task not found")
        return get_visual_todo_list(todo_list, TODO_VISUAL_FILTER)
    # Update todo task
    todo_task = cascade_todo_task(todo_task)
    current_duration = todo_task.keyval.get("duration", "0")
    todo_task.keyval["duration"] = add_durations(current_duration, ctx.input.duration)
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
    # save todo with log work
    with open(log_work_file_path, "w") as f:
        f.write(json.dumps(log_work, indent=2))
    # get log work list
    task_id = todo_task.keyval.get("id", "")
    log_work_path = os.path.join(TODO_DIR, "log-work", f"{task_id}.json")
    log_work_list = []
    if os.path.isfile(log_work_path):
        with open(log_work_path, "r") as f:
            log_work_list = json.loads(f.read())
    return "\n".join(
        [
            get_visual_todo_list(todo_list, TODO_VISUAL_FILTER),
            "",
            get_visual_todo_card(todo_task, log_work_list),
        ]
    )


def _get_default_start() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@make_task(
    name="edit-todo",
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
def edit_todo(ctx: AnyContext):
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
    return get_visual_todo_list(todo_list, TODO_VISUAL_FILTER)


def _get_todo_txt_content() -> str:
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    if not os.path.isfile(todo_file_path):
        return ""
    with open(todo_file_path, "r") as f:
        return f.read()
