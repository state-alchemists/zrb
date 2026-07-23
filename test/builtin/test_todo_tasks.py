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


def _find_input(task, name):
    return next(inp for inp in task.inputs if inp.name == name)


def _add_task(description, keyword_priority="A", project="", context=""):
    ctx = MagicMock()
    ctx.input.description = description
    ctx.input.priority = keyword_priority
    ctx.input.project = project
    ctx.input.context = context
    ctx.input.filter = ""
    return add_todo._action(ctx)


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


def test_add_todo_appends_to_existing_file(temp_todo_dir):
    # First add creates the file
    _add_task("first task")
    # Second add loads the existing file before appending (covers line 77)
    res = _add_task("second task")
    assert "first task" in res
    assert "second task" in res


def test_list_todo_loads_existing_file(temp_todo_dir):
    # Create a todo first so list_todo hits the load branch (covers line 114)
    _add_task("listed task")
    ctx = MagicMock()
    ctx.input.filter = ""
    res = list_todo._action(ctx)
    assert "listed task" in res


def test_show_todo_reads_existing_log_work(temp_todo_dir):
    # Add and log work so a log-work json exists for the task
    _add_task("logged task")
    ctx_log = MagicMock()
    ctx_log.input.keyword = "logged"
    ctx_log.input.duration = "30m"
    ctx_log.input.stop = "2024-01-01 12:00:00"
    ctx_log.input.log = "did stuff"
    ctx_log.input.filter = ""
    log_todo._action(ctx_log)

    # Show should read the existing log-work file (covers line 145)
    ctx_show = MagicMock()
    ctx_show.input.keyword = "logged"
    ctx_show.input.filter = ""
    res = show_todo._action(ctx_show)
    assert "logged task" in res


def test_complete_todo_not_found(temp_todo_dir):
    _add_task("existing task")
    ctx = MagicMock()
    ctx.input.keyword = "nonexistent"
    ctx.input.filter = ""
    res = complete_todo._action(ctx)
    ctx.log_error.assert_called_with("Task not found")
    assert res is not None


def test_complete_todo_already_completed(temp_todo_dir):
    _add_task("repeat task")
    # Complete once
    ctx_done = MagicMock()
    ctx_done.input.keyword = "repeat"
    ctx_done.input.filter = ""
    complete_todo._action(ctx_done)
    # Complete again -> already completed branch (covers lines 171-172)
    ctx_again = MagicMock()
    ctx_again.input.keyword = "repeat"
    ctx_again.input.filter = ""
    res = complete_todo._action(ctx_again)
    ctx_again.log_error.assert_called_with("Task already completed")
    assert res is not None


def test_archive_todo_makes_dir_when_missing(temp_todo_dir):
    # Old completed task so there is something to archive
    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    with open(todo_file, "w") as f:
        f.write("x 2000-01-01 2000-01-01 old done task\n")

    ctx = MagicMock()
    ctx.input.filter = ""
    # Force the "TODO_DIR not a directory" branch (covers line 214). makedirs is
    # mocked because the real dir exists (patched isdir would make makedirs raise).
    with (
        patch("zrb.builtin.todo.os.path.isdir", return_value=False),
        patch("zrb.builtin.todo.os.makedirs") as mock_makedirs,
    ):
        archive_todo._action(ctx)

    mock_makedirs.assert_any_call(temp_todo_dir, exist_ok=True)
    assert os.path.exists(os.path.join(temp_todo_dir, "archive.txt"))


def test_archive_todo_appends_to_existing_archive(temp_todo_dir):
    # Pre-existing archive file so the load branch runs (covers line 218)
    archive_file = os.path.join(temp_todo_dir, "archive.txt")
    with open(archive_file, "w") as f:
        f.write("x 1999-01-01 1999-01-01 previously archived\n")

    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    with open(todo_file, "w") as f:
        f.write("x 2000-01-01 2000-01-01 newly done task\n")

    ctx = MagicMock()
    ctx.input.filter = ""
    archive_todo._action(ctx)

    with open(archive_file, "r") as f:
        archive_content = f.read()
    assert "previously archived" in archive_content
    assert "newly done task" in archive_content


def test_log_todo_not_found(temp_todo_dir):
    _add_task("some task")
    ctx = MagicMock()
    ctx.input.keyword = "nonexistent"
    ctx.input.duration = "30m"
    ctx.input.stop = "2024-01-01 12:00:00"
    ctx.input.log = "note"
    ctx.input.filter = ""
    res = log_todo._action(ctx)
    ctx.log_error.assert_called_with("Task not found")
    assert res is not None


def test_log_todo_reads_existing_log_work(temp_todo_dir):
    _add_task("twice logged task")
    base_ctx = {
        "keyword": "twice",
        "duration": "30m",
        "stop": "2024-01-01 12:00:00",
        "log": "first",
        "filter": "",
    }

    def _make_ctx(log_text):
        ctx = MagicMock()
        ctx.input.keyword = base_ctx["keyword"]
        ctx.input.duration = base_ctx["duration"]
        ctx.input.stop = base_ctx["stop"]
        ctx.input.log = log_text
        ctx.input.filter = base_ctx["filter"]
        return ctx

    # First log creates the log-work file
    log_todo._action(_make_ctx("first"))
    # Second log reads the existing log-work file (covers line 279)
    res = log_todo._action(_make_ctx("second"))
    assert "DESCRIPTION" in res


def test_log_todo_stop_input_default(temp_todo_dir):
    # Resolving the "stop" input default invokes _get_default_stop_work_time_str
    # (covers line 316)
    stop_input = _find_input(log_todo, "stop")
    default_str = stop_input.get_default_str(MagicMock())
    # Format: %Y-%m-%d %H:%M:%S
    assert len(default_str) == len("2024-01-01 12:00:00")
    assert default_str.count(":") == 2


def test_edit_todo_text_default_no_file(temp_todo_dir):
    # No todo.txt present -> default resolves to empty string (covers lines 349-351)
    text_input = _find_input(edit_todo, "text")
    default_str = text_input.get_default_str(MagicMock())
    assert default_str == ""


def test_edit_todo_text_default_with_file(temp_todo_dir):
    # todo.txt present -> default reads its content (covers line 352)
    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    with open(todo_file, "w") as f:
        f.write("(A) existing content\n")
    text_input = _find_input(edit_todo, "text")
    default_str = text_input.get_default_str(MagicMock())
    assert "existing content" in default_str
