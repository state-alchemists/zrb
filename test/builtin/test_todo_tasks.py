import os
from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.todo import (
    add_todo,
    archive_todo,
    complete_todo,
    edit_todo,
    list_todo,
    log_todo,
    show_todo,
)


@pytest.fixture
def temp_todo_dir(tmp_path):
    todo_dir = tmp_path / "todo"
    todo_dir.mkdir()
    (todo_dir / "log-work").mkdir()
    # We patch the CFG in the module where todo tasks live
    with patch("zrb.builtin.todo.CFG") as mock_cfg:
        mock_cfg.TODO_DIR = str(todo_dir)
        mock_cfg.TODO_VISUAL_FILTER = ""
        mock_cfg.TODO_RETENTION = "7d"
        yield str(todo_dir)


def test_add_todo_complex(temp_todo_dir):
    ctx = MagicMock()
    ctx.input.description = "task 1"
    ctx.input.priority = "A"
    ctx.input.project = "p1 p2"
    ctx.input.context = "c1 c2"
    ctx.input.filter = ""

    # Bypass BaseTask and call underlying function
    res = add_todo._action(ctx)
    assert "task 1" in res
    assert os.path.exists(os.path.join(temp_todo_dir, "todo.txt"))


def test_list_todo_basic(temp_todo_dir):
    ctx = MagicMock()
    ctx.input.filter = ""
    res = list_todo._action(ctx)
    assert res is not None


def test_show_todo_lifecycle(temp_todo_dir):
    # Add a task first
    ctx_add = MagicMock()
    ctx_add.input.description = "show me"
    ctx_add.input.priority = "B"
    ctx_add.input.project = ""
    ctx_add.input.context = ""
    ctx_add.input.filter = ""
    add_todo._action(ctx_add)

    # Show it
    ctx_show = MagicMock()
    ctx_show.input.keyword = "show"
    ctx_show.input.filter = ""
    res = show_todo._action(ctx_show)
    assert "show me" in res


def test_show_todo_not_found(temp_todo_dir):
    ctx = MagicMock()
    ctx.input.keyword = "nonexistent"
    ctx.input.filter = ""
    show_todo._action(ctx)
    ctx.log_error.assert_called_with("Task not found")


def test_log_todo(temp_todo_dir):
    # Add
    ctx_add = MagicMock()
    ctx_add.input.description = "work task"
    ctx_add.input.priority = "C"
    ctx_add.input.project = ""
    ctx_add.input.context = ""
    ctx_add.input.filter = ""
    add_todo._action(ctx_add)

    # Log
    ctx_log = MagicMock()
    ctx_log.input.keyword = "work"
    ctx_log.input.duration = "1h"
    ctx_log.input.stop = "2024-01-01 12:00:00"
    ctx_log.input.log = ""
    ctx_log.input.filter = ""
    res = log_todo._action(ctx_log)
    assert "DESCRIPTION" in res


def test_complete_todo(temp_todo_dir):
    # Add
    ctx_add = MagicMock()
    ctx_add.input.description = "done task"
    ctx_add.input.priority = "D"
    ctx_add.input.project = ""
    ctx_add.input.context = ""
    ctx_add.input.filter = ""
    add_todo._action(ctx_add)

    # Complete
    ctx_done = MagicMock()
    ctx_done.input.keyword = "done"
    ctx_done.input.filter = ""
    res = complete_todo._action(ctx_done)
    assert "COMPLETED AT" in res

    # Try to show completed (should fail)
    ctx_show = MagicMock()
    ctx_show.input.keyword = "done"
    ctx_show.input.filter = ""
    show_todo._action(ctx_show)
    ctx_show.log_error.assert_called_with("Task already completed")


def test_edit_todo(temp_todo_dir):
    ctx = MagicMock()
    ctx.input.text = "A new task\nB another task"
    ctx.input.filter = ""
    res = edit_todo._action(ctx)
    assert "new task" in res
    assert "another task" in res

    with open(os.path.join(temp_todo_dir, "todo.txt"), "r") as f:
        content = f.read()
    assert "new task" in content


def test_archive_todo_empty(temp_todo_dir):
    ctx = MagicMock()
    ctx.input.filter = ""
    res = archive_todo._action(ctx)
    assert res is not None


def test_archive_todo_with_done_tasks(temp_todo_dir):
    # Add a done task manually to todo.txt with an OLD date
    # Format: x completion_date creation_date description
    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    with open(todo_file, "w") as f:
        f.write("x 2000-01-01 2000-01-01 done task\n")

    ctx = MagicMock()
    ctx.input.filter = ""
    archive_todo._action(ctx)

    # Check filesystem
    with open(todo_file, "r") as f:
        content = f.read()
    assert "done task" not in content
    assert os.path.exists(os.path.join(temp_todo_dir, "archive.txt"))
