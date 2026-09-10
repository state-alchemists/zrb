import datetime
from unittest.mock import patch

import pytest

from zrb.util.todo.model import TodoTaskModel
from zrb.util.todo.parser import (
    cascade_todo_task,
    line_to_todo_task,
    load_todo_list,
    save_todo_list,
    select_todo_task,
    todo_task_to_line,
)


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


@patch("zrb.util.todo.parser.read_file")
def test_load_todo_list(mock_read_file):
    mock_read_file.return_value = """
    (A) 2023-10-26 Task 1 +p1
    2023-10-27 Task 2 @c1
    """
    todo_list = load_todo_list("dummy.txt")
    assert len(todo_list) == 2
    assert todo_list[0].description == "Task 1"
    assert todo_list[1].description == "Task 2"


@patch("zrb.util.todo.parser.write_file")
def test_save_todo_list(mock_write_file, sample_task):
    todo_list = [sample_task]
    save_todo_list("dummy.txt", todo_list)
    mock_write_file.assert_called_once()
    # Check if content passed to write_file contains expected string
    args, _ = mock_write_file.call_args
    assert args[0] == "dummy.txt"
    assert len(args[1]) == 1
    assert "Buy milk" in args[1][0]


class TestSelectTodoTask:
    """More comprehensive tests for select_todo_task."""

    def test_exact_description_match(self, sample_task):
        todo_list = [sample_task]
        result = select_todo_task(todo_list, "Buy milk")
        assert result == sample_task

    def test_partial_id_match(self, sample_task):
        todo_list = [sample_task]
        # Partial ID match
        result = select_todo_task(todo_list, "1")
        # Should match by ID first
        assert result == sample_task

    def test_exact_then_partial_match_order(self):
        # Create two tasks where one has matching ID and other has matching description
        task1 = TodoTaskModel(description="First task", keyval={"id": "abc"})
        task2 = TodoTaskModel(description="Second abc task", keyval={"id": "xyz"})
        todo_list = [task1, task2]
        # Partial match "abc" should match task1 by ID first
        result = select_todo_task(todo_list, "abc")
        assert result == task1


class TestLoadTodoList:
    """Tests for load_todo_list edge cases."""

    def test_empty_file(self):
        with patch("zrb.util.todo.parser.read_file") as mock_read:
            mock_read.return_value = ""
            todo_list = load_todo_list("empty.txt")
            assert len(todo_list) == 0

    def test_whitespace_only_lines(self):
        with patch("zrb.util.todo.parser.read_file") as mock_read:
            mock_read.return_value = "   \n\n   \n"
            todo_list = load_todo_list("whitespace.txt")
            assert len(todo_list) == 0


class TestLineToTodoTask:
    """More tests for line_to_todo_task variations."""

    def test_line_with_only_priority(self):
        line = "(B) Buy groceries"
        task = line_to_todo_task(line)
        assert task.priority == "B"
        assert task.description == "Buy groceries"

    def test_line_with_single_date_sets_creation_date(self):
        # When only one date is present, it's treated as creation_date
        line = "x 2023-10-27 Buy groceries"
        task = line_to_todo_task(line)
        assert task.completed is True
        # Single date gets assigned to creation_date
        assert task.creation_date == datetime.date(2023, 10, 27)

    def test_line_with_both_dates_no_priority(self):
        line = "x 2023-10-27 2023-10-26 Buy groceries"
        task = line_to_todo_task(line)
        assert task.completed is True
        assert task.completion_date == datetime.date(2023, 10, 27)
        assert task.creation_date == datetime.date(2023, 10, 26)


class TestTodoTaskToLine:
    """Tests for todo_task_to_line variations."""

    def test_completed_task_with_dates(self):
        task = TodoTaskModel(
            description="Done task",
            completed=True,
            priority="A",
            creation_date=datetime.date(2023, 10, 26),
            completion_date=datetime.date(2023, 10, 27),
        )
        line = todo_task_to_line(task)
        assert line.startswith("x (A) 2023-10-27 2023-10-26 Done task")

    def test_task_default_priority(self):
        # TodoTaskModel has a default priority
        task = TodoTaskModel(
            description="Simple task",
            completed=False,
        )
        line = todo_task_to_line(task)
        # Default priority is 'D'
        assert "(D)" in line
        assert "Simple task" in line


class TestCascadeTodoTask:
    """Tests for cascade_todo_task edge cases."""

    def test_cascade_with_existing_id(self):
        task = TodoTaskModel(
            description="Task with ID",
            keyval={"id": "existing"},
        )
        cascaded = cascade_todo_task(task)
        # Should not overwrite existing ID
        assert cascaded.keyval["id"] == "existing"

    def test_cascade_with_existing_date(self):
        task = TodoTaskModel(
            description="Task with date",
            creation_date=datetime.date(2023, 1, 1),
        )
        cascaded = cascade_todo_task(task)
        # Should not overwrite existing date
        assert cascaded.creation_date == datetime.date(2023, 1, 1)
