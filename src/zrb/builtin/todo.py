import datetime
import json
import os
from typing import Any

from zrb.builtin.group import todo_group
from zrb.config import TODO_DIR, TODO_RETENTION, TODO_VISUAL_FILTER
from zrb.context.any_context import AnyContext
from zrb.input.str_input import StrInput
from zrb.input.text_input import TextInput
from zrb.task.make_task import make_task
from zrb.util.file import read_file, write_file
from zrb.util.todo import (
    TodoTaskModel,
    add_duration,
    cascade_todo_task,
    get_visual_todo_card,
    get_visual_todo_list,
    line_to_todo_task,
    load_todo_list,
    parse_duration,
    save_todo_list,
    select_todo_task,
    todo_task_to_line,
)


def _get_filter_input(allow_positional_parsing: bool = False) -> StrInput:
    return StrInput(
        name="filter",
        description="Visual filter",
        prompt="Visual Filter",
        allow_empty=True,
        allow_positional_parsing=allow_positional_parsing,
        always_prompt=False,
        default=TODO_VISUAL_FILTER,
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
            default="E",
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
        _get_filter_input(),
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
    return get_visual_todo_list(todo_list, filter=ctx.input.filter)


@make_task(
    name="list-todo",
    input=_get_filter_input(allow_positional_parsing=True),
    description="📋 List todo",
    group=todo_group,
    alias="list",
)
def list_todo(ctx: AnyContext):
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    todo_list: list[TodoTaskModel] = []
    if os.path.isfile(todo_file_path):
        todo_list = load_todo_list(todo_file_path)
    return get_visual_todo_list(todo_list, filter=ctx.input.filter)


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
        log_work_list = json.loads(read_file(log_work_path))
    return get_visual_todo_card(todo_task, log_work_list)


@make_task(
    name="complete-todo",
    input=[
        StrInput(name="keyword", prompt="Task keyword", description="Task Keyword"),
        _get_filter_input(),
    ],
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
        return get_visual_todo_list(todo_list, filter=ctx.input.filter)
    if todo_task.completed:
        ctx.log_error("Task already completed")
        return get_visual_todo_list(todo_list, filter=ctx.input.filter)
    # Update todo task
    todo_task = cascade_todo_task(todo_task)
    if todo_task.creation_date is not None:
        todo_task.completion_date = datetime.date.today()
    todo_task.completed = True
    # Save todo list
    save_todo_list(todo_file_path, todo_list)
    return get_visual_todo_list(todo_list, filter=ctx.input.filter)


@make_task(
    name="archive-todo",
    input=_get_filter_input(),
    description="📚 Archive todo",
    group=todo_group,
    alias="archive",
)
def archive_todo(ctx: AnyContext):
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    todo_list: list[TodoTaskModel] = []
    if os.path.isfile(todo_file_path):
        todo_list = load_todo_list(todo_file_path)
    retention_duration = datetime.timedelta(seconds=parse_duration(TODO_RETENTION))
    threshold_date = datetime.date.today() - retention_duration
    new_archived_todo_list = [
        todo_task
        for todo_task in todo_list
        if todo_task.completed
        and todo_task.completion_date is not None
        and todo_task.completion_date < threshold_date
    ]
    working_todo_list = [
        todo_task for todo_task in todo_list if todo_task not in new_archived_todo_list
    ]
    if len(new_archived_todo_list) == 0:
        ctx.print("No completed task to archive")
        return get_visual_todo_list(todo_list, filter=ctx.input.filter)
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
    return get_visual_todo_list(todo_list, filter=ctx.input.filter)


@make_task(
    name="log-todo",
    input=[
        StrInput(name="keyword", prompt="Task keyword", description="Task Keyword"),
        StrInput(
            name="log",
            prompt="Working log",
            description="Working log",
        ),
        StrInput(
            name="duration",
            prompt="Working duration",
            description="Working duration",
            default="30m",
        ),
        StrInput(
            name="stop",
            prompt="Working stop time (%Y-%m-%d %H:%M:%S)",
            description="Working stop time",
            default=lambda _: _get_default_stop_work_time_str(),
        ),
        _get_filter_input(),
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
        return get_visual_todo_list(todo_list, filter=ctx.input.filter)
    # Update todo task
    todo_task = cascade_todo_task(todo_task)
    current_duration_str = todo_task.keyval.get("duration", "0")
    todo_task.keyval["duration"] = add_duration(
        current_duration_str, ctx.input.duration
    )
    # Save todo list
    save_todo_list(todo_file_path, todo_list)
    # Add log work
    log_work_dir = os.path.join(TODO_DIR, "log-work")
    os.makedirs(log_work_dir, exist_ok=True)
    log_work_file_path = os.path.join(
        log_work_dir, f"{todo_task.keyval.get('id')}.json"
    )
    if os.path.isfile(log_work_file_path):
        log_work_json = read_file(log_work_file_path)
    else:
        log_work_json = "[]"
    log_work: list[dict[str, Any]] = json.loads(log_work_json)
    start_work_time_str = _get_start_work_time_str(ctx.input.stop, ctx.input.duration)
    log_work.append(
        {
            "log": ctx.input.log,
            "duration": ctx.input.duration,
            "start": start_work_time_str,
        }
    )
    # save todo with log work
    write_file(log_work_file_path, json.dumps(log_work, indent=2))
    # get log work list
    task_id = todo_task.keyval.get("id", "")
    log_work_path = os.path.join(TODO_DIR, "log-work", f"{task_id}.json")
    log_work_list = []
    if os.path.isfile(log_work_path):
        log_work_list = json.loads(read_file(log_work_path))
    return "\n".join(
        [
            get_visual_todo_list(todo_list, filter=ctx.input.filter),
            "",
            get_visual_todo_card(todo_task, log_work_list),
        ]
    )


def _get_start_work_time_str(stop_work_time_str: str, work_duration_str: str) -> str:
    work_duration = parse_duration(work_duration_str)
    stop_work_time = datetime.datetime.strptime(stop_work_time_str, "%Y-%m-%d %H:%M:%S")
    start_work_time = stop_work_time - datetime.timedelta(seconds=work_duration)
    return start_work_time.strftime("%Y-%m-%d %H:%M:%S")


def _get_default_stop_work_time_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@make_task(
    name="edit-todo",
    input=[
        TextInput(
            name="text",
            description="Todo.txt content",
            prompt="Todo.txt content (will override existing)",
            default=lambda _: _get_todo_txt_content(),
            allow_positional_parsing=False,
        ),
        _get_filter_input(),
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
    write_file(todo_file_path, new_content)
    todo_list = load_todo_list(todo_file_path)
    return get_visual_todo_list(todo_list, filter=ctx.input.filter)


def _get_todo_txt_content() -> str:
    todo_file_path = os.path.join(TODO_DIR, "todo.txt")
    if not os.path.isfile(todo_file_path):
        return ""
    return read_file(todo_file_path)
