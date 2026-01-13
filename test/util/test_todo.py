import datetime
from unittest.mock import MagicMock, patch

import pytest

from zrb.util.todo import (
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
from zrb.util.todo_model import TodoTaskModel


@pytest.fixture
def sample_task():
    return TodoTaskModel(
        description="Buy milk",
        priority="A",
        completed=False,
        creation_date=datetime.date(2023, 10, 26),
        completion_date=None,
        projects=["groceries"],
        contexts=["shop"],
        keyval={"id": "1"},
    )


def test_line_to_todo_task_full():
    line = "x (A) 2023-10-27 2023-10-26 Buy milk +groceries @shop id:1"
    task = line_to_todo_task(line)
    assert task.completed is True
    assert task.priority == "A"
    assert task.completion_date == datetime.date(2023, 10, 27)
    assert task.creation_date == datetime.date(2023, 10, 26)
    assert task.description == "Buy milk"
    assert task.projects == ["groceries"]
    assert task.contexts == ["shop"]
    assert task.keyval == {"id": "1"}


def test_line_to_todo_task_minimal():
    line = "Buy milk"
    task = line_to_todo_task(line)
    assert task.completed is False
    assert task.priority is None
    assert task.creation_date is None
    assert task.description == "Buy milk"


def test_todo_task_to_line(sample_task):
    line = todo_task_to_line(sample_task)
    # Note: dictionary order is insertion order in modern Python, assuming deterministic
    expected = "(A) 2023-10-26 Buy milk +groceries @shop id:1"
    assert line == expected


def test_cascade_todo_task(sample_task):
    task = TodoTaskModel(description="New task")
    cascaded = cascade_todo_task(task)
    assert cascaded.creation_date == datetime.date.today()
    assert "id" in cascaded.keyval


def test_select_todo_task(sample_task):
    todo_list = [sample_task]

    # Select by exact ID
    assert select_todo_task(todo_list, "1") == sample_task
    # Select by description substring
    assert select_todo_task(todo_list, "Buy") == sample_task
    # No match
    assert select_todo_task(todo_list, "Cheese") is None


@patch("zrb.util.todo.read_file")
def test_load_todo_list(mock_read_file):
    mock_read_file.return_value = """
    (A) 2023-10-26 Task 1 +p1
    2023-10-27 Task 2 @c1
    """
    todo_list = load_todo_list("dummy.txt")
    assert len(todo_list) == 2
    assert todo_list[0].description == "Task 1"
    assert todo_list[1].description == "Task 2"


@patch("zrb.util.todo.write_file")
def test_save_todo_list(mock_write_file, sample_task):
    todo_list = [sample_task]
    save_todo_list("dummy.txt", todo_list)
    mock_write_file.assert_called_once()
    # Check if content passed to write_file contains expected string
    args, _ = mock_write_file.call_args
    assert args[0] == "dummy.txt"
    assert len(args[1]) == 1
    assert "Buy milk" in args[1][0]


def test_duration_parsing():
    assert parse_duration("1h") == 3600
    assert parse_duration("1m") == 60
    assert parse_duration("1h30m") == 5400
    assert parse_duration("1d") == 86400


def test_add_duration():
    assert add_duration("1h", "30m") == "1h30m"
    assert add_duration("50m", "20m") == "1h10m"


def test_get_visual_todo_list(sample_task):
    # Just ensure it doesn't crash and returns string
    visual = get_visual_todo_list([sample_task], filter="")
    assert "Buy milk" in visual
    assert "DESCRIPTION" in visual  # Header check


def test_get_visual_todo_card(sample_task):
    card = get_visual_todo_card(
        sample_task, [{"log": "worked", "duration": "1h", "start": "now"}]
    )
    assert "Buy milk" in card
    assert "worked" in card
    assert "1h" in card
