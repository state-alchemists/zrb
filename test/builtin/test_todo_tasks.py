import datetime
import os
from unittest.mock import MagicMock, patch
import pytest
from zrb.builtin.todo import add_todo, archive_todo, complete_todo, edit_todo, list_todo, log_todo, show_todo
from zrb.context.shared_context import SharedContext
from zrb.session.session import Session
from zrb.config.config import CFG

@pytest.fixture
def temp_todo_dir(tmp_path):
    d = tmp_path / "todo"
    d.mkdir()
    with patch.dict(os.environ, {"ZRB_TODO_DIR": str(d)}):
        yield str(d)

def get_session():
    return Session(shared_ctx=SharedContext(), state_logger=MagicMock())

@pytest.mark.asyncio
async def test_todo_lifecycle_behavior(temp_todo_dir):
    # 1. Add
    await add_todo.async_run(session=get_session(), kwargs={
        "priority": "A", "description": "Task 1", "context": "work", "project": "zrb", "filter": ""
    })
    assert os.path.exists(os.path.join(temp_todo_dir, "todo.txt"))

    # 2. List
    res = await list_todo.async_run(session=get_session(), kwargs={"filter": ""})
    assert "Task 1" in str(res)

    # 3. Show
    res = await show_todo.async_run(session=get_session(), kwargs={"keyword": "Task 1", "filter": ""})
    assert "Task 1" in str(res)

    # 4. Complete
    await complete_todo.async_run(session=get_session(), kwargs={"keyword": "Task 1", "filter": ""})
    with open(os.path.join(temp_todo_dir, "todo.txt"), "r") as f:
        todo_content = f.read()
        assert todo_content.startswith("x ")
    
    # Manually set completion date to 10 days ago to ensure it's archived
    ten_days_ago = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
    # The format is 'x (A) 2026-03-18 2026-03-18 Task 1 +zrb @work id:...'
    # Completion date is the first date.
    new_todo_content = todo_content.replace(datetime.date.today().isoformat(), ten_days_ago, 1)
    with open(os.path.join(temp_todo_dir, "todo.txt"), "w") as f:
        f.write(new_todo_content)

    # 5. Archive
    # Manually override and restore because Config property has no deleter for patch.object
    original_retention = CFG.TODO_RETENTION
    CFG.TODO_RETENTION = "0s"
    try:
        await archive_todo.async_run(session=get_session(), kwargs={"filter": ""})
    finally:
        CFG.TODO_RETENTION = original_retention
    assert os.path.exists(os.path.join(temp_todo_dir, "archive.txt"))

@pytest.mark.asyncio
async def test_log_todo_behavior(temp_todo_dir):
    await add_todo.async_run(session=get_session(), kwargs={
        "priority": "A", "description": "Log Task", "context": "", "project": "", "filter": ""
    })

    res = await log_todo.async_run(session=get_session(), kwargs={
        "keyword": "Log Task", "log": "Working", "duration": "10m",
        "stop": "2026-02-18 10:00:00", "filter": ""
    })
    assert "Log Task" in str(res)
    assert "Working" in str(res)

@pytest.mark.asyncio
async def test_edit_todo_behavior(temp_todo_dir):
    await edit_todo.async_run(session=get_session(), kwargs={
        "text": "(A) Edited task", "filter": ""
    })
    with open(os.path.join(temp_todo_dir, "todo.txt"), "r") as f:
        assert "Edited task" in f.read()
