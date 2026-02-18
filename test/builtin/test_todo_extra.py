import os
import shutil
from unittest.mock import MagicMock

from zrb.builtin.todo import (
    add_todo,
    archive_todo,
    complete_todo,
    edit_todo,
    list_todo,
    log_todo,
    show_todo,
)
from zrb.config.config import CFG
from zrb.context.any_context import AnyContext


def setup_module(module):
    CFG.TODO_DIR = "temp_todo"
    if os.path.exists(CFG.TODO_DIR):
        shutil.rmtree(CFG.TODO_DIR)
    os.makedirs(CFG.TODO_DIR)


def teardown_module(module):
    if os.path.exists(CFG.TODO_DIR):
        shutil.rmtree(CFG.TODO_DIR)


def test_todo_flow_coverage():
    ctx = MagicMock()
    ctx.input.priority = "A"
    ctx.input.description = "Task 1"
    ctx.input.context = "work"
    ctx.input.project = "zrb"
    ctx.input.filter = ""

    # 1. Add todo (triggers branch for existing file)
    add_todo._action(ctx)
    add_todo._action(ctx)  # Twice to trigger load_todo_list branch

    # 2. List todo
    list_todo._action(ctx)

    # 3. Show todo
    ctx.input.keyword = "Task 1"
    show_todo._action(ctx)

    # 4. Show todo not found
    ctx.input.keyword = "Nonexistent"
    show_todo._action(ctx)

    # 5. Complete todo
    ctx.input.keyword = "Task 1"
    complete_todo._action(ctx)

    # 6. Archive todo (with retention)
    # Set retention to 0s to archive immediately
    CFG.TODO_RETENTION = "0s"
    archive_todo._action(ctx)


def test_edit_todo_coverage():
    ctx = MagicMock()
    ctx.input.text = "A (B) Task 1\nB Task 2"
    ctx.input.filter = ""
    edit_todo._action(ctx)


def test_log_todo_coverage():
    # Setup: add a task first
    ctx = MagicMock()
    ctx.input.priority = "A"
    ctx.input.description = "Task for log"
    ctx.input.context = ""
    ctx.input.project = ""
    ctx.input.filter = ""
    add_todo._action(ctx)

    ctx.input.keyword = "Task for log"
    ctx.input.log = "Working on it"
    ctx.input.duration = "10m"
    ctx.input.stop = "2026-02-18 10:00:00"
    log_todo._action(ctx)

    # Log again to trigger existing log work file branch
    log_todo._action(ctx)
