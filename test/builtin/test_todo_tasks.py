import datetime
import os
from unittest.mock import patch

import pytest

from zrb.builtin.todo import (
    add_todo,
    archive_todo,
    complete_todo,
    edit_todo,
    list_todo,
    log_todo,
)
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session


def get_fresh_session():
    shared_ctx = SharedContext()
    session = Session(shared_ctx=shared_ctx)
    return session


@pytest.fixture
def temp_todo_dir(tmp_path):
    d = tmp_path / "todo"
    d.mkdir()
    with patch.dict(os.environ, {"ZRB_TODO_DIR": str(d)}):
        yield str(d)


@pytest.mark.asyncio
async def test_add_todo_task(temp_todo_dir):
    task = add_todo
    session = get_fresh_session()
    session.set_main_task(task)
    res = await task.async_run(
        session=session,
        kwargs={
            "priority": "A",
            "description": "Test Task",
            "context": "work",
            "project": "zrb",
            "filter": "",
        },
    )
    assert "Test Task" in res
    assert os.path.exists(os.path.join(temp_todo_dir, "todo.txt"))


@pytest.mark.asyncio
async def test_list_todo_task(temp_todo_dir):
    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    with open(todo_file, "w") as f:
        f.write("(A) Test Task +zrb @work\n")
    task = list_todo
    session = get_fresh_session()
    session.set_main_task(task)
    res = await task.async_run(session=session, kwargs={"filter": ""})
    assert "Test Task" in res


@pytest.mark.asyncio
async def test_complete_todo_task(temp_todo_dir):
    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    with open(todo_file, "w") as f:
        f.write("(A) Test Task\n")
    task = complete_todo
    session = get_fresh_session()
    session.set_main_task(task)
    res = await task.async_run(session=session, kwargs={"keyword": "Test", "filter": ""})
    assert "Test Task" in res
    with open(todo_file, "r") as f:
        content = f.read()
        assert content.startswith("x ")


@pytest.mark.asyncio
async def test_archive_todo_task(temp_todo_dir):
    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    old_date = (datetime.date.today() - datetime.timedelta(weeks=3)).strftime(
        "%Y-%m-%d"
    )
    with open(todo_file, "w") as f:
        f.write(f"x {old_date} {old_date} Old Task\n")
    task = archive_todo
    session = get_fresh_session()
    session.set_main_task(task)
    res = await task.async_run(session=session, kwargs={"filter": ""})
    assert "Old Task" not in res
    assert os.path.exists(os.path.join(temp_todo_dir, "archive.txt"))


@pytest.mark.asyncio
async def test_log_todo_task(temp_todo_dir):
    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    with open(todo_file, "w") as f:
        f.write("(A) Task to log id:1\n")
    task = log_todo
    session = get_fresh_session()
    session.set_main_task(task)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    res = await task.async_run(
        session=session,
        kwargs={
            "keyword": "Task",
            "log": "Worked on it",
            "duration": "1h",
            "stop": now,
            "filter": "",
        },
    )
    assert "Task to log" in res
    assert "Worked on it" in res


@pytest.mark.asyncio
async def test_edit_todo_task(temp_todo_dir):
    task = edit_todo
    session = get_fresh_session()
    session.set_main_task(task)
    res = await task.async_run(
        session=session,
        kwargs={"text": "(A) New content\n(B) Second task", "filter": ""},
    )
    assert "New content" in res
    assert "Second task" in res
    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    with open(todo_file, "r") as f:
        content = f.read()
        assert "New content" in content
        assert "Second task" in content
