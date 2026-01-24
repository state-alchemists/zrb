import datetime
import os
import shutil
from unittest.mock import MagicMock, patch

import pytest

from zrb.builtin.todo import (
    add_todo,
    archive_todo,
    complete_todo,
    edit_todo,
    list_todo,
    log_todo,
)
from zrb.config.config import CFG


@pytest.fixture
def temp_todo_dir(tmp_path):
    d = tmp_path / "todo"
    d.mkdir()
    # Mocking environment variable is safer for these properties
    with patch.dict(os.environ, {"ZRB_TODO_DIR": str(d)}):
        # We need to make sure CFG reflects this change
        # Since it reads from os.environ, it should be fine if we use it after patch
        yield str(d)


@pytest.mark.asyncio
async def test_add_todo_task(temp_todo_dir):
    ctx = MagicMock()
    ctx.input.priority = "A"
    ctx.input.description = "Test Task"
    ctx.input.context = "work"
    ctx.input.project = "zrb"
    ctx.input.filter = ""

    # add_todo is a BaseTask, so we call its _exec_action or action
    res = await add_todo._exec_action(ctx)
    assert "Test Task" in res
    assert os.path.exists(os.path.join(temp_todo_dir, "todo.txt"))


@pytest.mark.asyncio
async def test_list_todo_task(temp_todo_dir):
    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    with open(todo_file, "w") as f:
        f.write("(A) Test Task +zrb @work\n")

    ctx = MagicMock()
    ctx.input.filter = ""

    res = await list_todo._exec_action(ctx)
    assert "Test Task" in res


@pytest.mark.asyncio
async def test_complete_todo_task(temp_todo_dir):
    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    with open(todo_file, "w") as f:
        f.write("(A) Test Task\n")

    ctx = MagicMock()
    # keyword is used in select_todo_task
    ctx.input.keyword = "Test"
    ctx.input.filter = ""

    res = await complete_todo._exec_action(ctx)
    assert "Test Task" in res
    with open(todo_file, "r") as f:
        content = f.read()
        assert content.startswith("x ")


@pytest.mark.asyncio
async def test_archive_todo_task(temp_todo_dir):
    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    # Creation date should be old enough to be archived (default retention 2w)
    old_date = (datetime.date.today() - datetime.timedelta(weeks=3)).strftime(
        "%Y-%m-%d"
    )
    with open(todo_file, "w") as f:
        f.write(f"x {old_date} {old_date} Old Task\n")

    ctx = MagicMock()
    ctx.input.filter = ""

    res = await archive_todo._exec_action(ctx)
    assert "Old Task" not in res
    assert os.path.exists(os.path.join(temp_todo_dir, "archive.txt"))


@pytest.mark.asyncio
async def test_log_todo_task(temp_todo_dir):
    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    with open(todo_file, "w") as f:
        f.write("(A) Task to log id:1\n")

    ctx = MagicMock()
    ctx.input.keyword = "Task"
    ctx.input.log = "Worked on it"
    ctx.input.duration = "1h"
    ctx.input.stop = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ctx.input.filter = ""

    res = await log_todo._exec_action(ctx)
    assert "Task to log" in res
    assert "Worked on it" in res


@pytest.mark.asyncio
async def test_edit_todo_task(temp_todo_dir):
    ctx = MagicMock()
    ctx.input.text = "(A) New content\n(B) Second task"
    ctx.input.filter = ""

    res = await edit_todo._exec_action(ctx)
    assert "New content" in res
    assert "Second task" in res

    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    with open(todo_file, "r") as f:
        content = f.read()
        assert "New content" in content
        assert "Second task" in content
