"""Where `TodoManager` persists a session's todos (`zrb/llm/tool/plan.py`)."""

import json

import pytest

from zrb.llm.tool.plan import todo_manager


@pytest.fixture
def todo_dir(tmp_path):
    saved_dir, saved_todos = todo_manager.todo_dir, todo_manager.todos
    todo_manager.todos = {}
    yield tmp_path / "gone" / "todos"
    todo_manager.todo_dir, todo_manager.todos = saved_dir, saved_todos


def test_saving_creates_a_todo_directory_that_is_missing(todo_dir):
    """The directory can vanish after the manager was created, or be pointed at a
    new place; without it a save fails with only a printed warning."""
    todo_manager.todo_dir = todo_dir

    todo_manager.write_todos("session", [{"content": "ship it"}])

    saved = json.loads((todo_dir / "session.json").read_text(encoding="utf-8"))
    assert saved["todos"][0]["content"] == "ship it"


def test_a_saved_list_is_read_back_by_a_fresh_cache(todo_dir):
    todo_manager.todo_dir = todo_dir
    todo_manager.write_todos("session", [{"content": "ship it"}])
    todo_manager.todos = {}

    reloaded = todo_manager.get_todos("session")

    assert reloaded is not None
    assert reloaded["todos"][0]["content"] == "ship it"
