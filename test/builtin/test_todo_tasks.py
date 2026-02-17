import datetime
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
)
from zrb.session.session import Session
from zrb.context.shared_context import SharedContext


@pytest.fixture
def temp_todo_dir(tmp_path):
    d = tmp_path / "todo"
    d.mkdir()
    # Mocking environment variable is safer for these properties
    with patch.dict(os.environ, {"ZRB_TODO_DIR": str(d)}):
        yield str(d)


@pytest.fixture
def mock_print():
    return MagicMock()


@pytest.fixture
def session(mock_print):
    shared_ctx = SharedContext(print_fn=mock_print)
    return Session(shared_ctx=shared_ctx, state_logger=MagicMock())


@pytest.mark.asyncio
async def test_add_todo_task(temp_todo_dir, session):
    # Execute publicly
    res = await add_todo.async_run(
        session=session,
        kwargs={
            "priority": "A",
            "description": "Test Task",
            "context": "work",
            "project": "zrb",
            "filter": ""
        }
    )
    assert "Test Task" in res
    assert os.path.exists(os.path.join(temp_todo_dir, "todo.txt"))


@pytest.mark.asyncio
async def test_list_todo_task(temp_todo_dir, session):
    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    with open(todo_file, "w") as f:
        f.write("(A) Test Task +zrb @work\n")

    res = await list_todo.async_run(session=session, kwargs={"filter": ""})
    assert "Test Task" in res


@pytest.mark.asyncio
async def test_complete_todo_task(temp_todo_dir, session):
    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    with open(todo_file, "w") as f:
        f.write("(A) Test Task\n")

    res = await complete_todo.async_run(
        session=session,
        kwargs={"keyword": "Test", "filter": ""}
    )
    assert "Test Task" in res
    with open(todo_file, "r") as f:
        content = f.read()
        assert content.startswith("x ")


@pytest.mark.asyncio
async def test_archive_todo_task(temp_todo_dir, session):
    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    # Creation date should be old enough to be archived (default retention 2w)
    old_date = (datetime.date.today() - datetime.timedelta(weeks=3)).strftime(
        "%Y-%m-%d"
    )
    with open(todo_file, "w") as f:
        f.write(f"x {old_date} {old_date} Old Task\n")

    res = await archive_todo.async_run(session=session, kwargs={"filter": ""})
    assert "Old Task" not in res
    assert os.path.exists(os.path.join(temp_todo_dir, "archive.txt"))


@pytest.mark.asyncio
async def test_log_todo_task(temp_todo_dir, session):
    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    with open(todo_file, "w") as f:
        f.write("(A) Task to log id:1\n")

    res = await log_todo.async_run(
        session=session,
        kwargs={
            "keyword": "Task",
            "log": "Worked on it",
            "duration": "1h",
            "stop": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "filter": ""
        }
    )
    assert "Task to log" in res
    assert "Worked on it" in res


@pytest.mark.asyncio
async def test_edit_todo_task(temp_todo_dir, session):
    res = await edit_todo.async_run(
        session=session,
        kwargs={
            "text": "(A) New content\n(B) Second task",
            "filter": ""
        }
    )
    assert "New content" in res
    assert "Second task" in res

    todo_file = os.path.join(temp_todo_dir, "todo.txt")
    with open(todo_file, "r") as f:
        content = f.read()
        assert "New content" in content
        assert "Second task" in content
