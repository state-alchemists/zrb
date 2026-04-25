import datetime
from unittest.mock import MagicMock, patch

import pytest

from zrb.util.todo import (
    add_duration,
    cascade_todo_task,
    get_visual_todo_card,
    get_visual_todo_line,
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


@patch("zrb.util.todo_parser.read_file")
def test_load_todo_list(mock_read_file):
    mock_read_file.return_value = """
    (A) 2023-10-26 Task 1 +p1
    2023-10-27 Task 2 @c1
    """
    todo_list = load_todo_list("dummy.txt")
    assert len(todo_list) == 2
    assert todo_list[0].description == "Task 1"
    assert todo_list[1].description == "Task 2"


@patch("zrb.util.todo_parser.write_file")
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
        with patch("zrb.util.todo_parser.read_file") as mock_read:
            mock_read.return_value = ""
            todo_list = load_todo_list("empty.txt")
            assert len(todo_list) == 0

    def test_whitespace_only_lines(self):
        with patch("zrb.util.todo_parser.read_file") as mock_read:
            mock_read.return_value = "   \n\n   \n"
            todo_list = load_todo_list("whitespace.txt")
            assert len(todo_list) == 0


class TestGetVisualTodoList:
    """Tests for get_visual_todo_list variations."""

    def test_empty_list(self):
        visual = get_visual_todo_list([], filter="")
        assert "Empty todo list" in visual

    def test_filter_by_description(self, sample_task):
        todo_list = [sample_task]
        visual = get_visual_todo_list(todo_list, filter="milk")
        assert "Buy milk" in visual

    def test_filter_by_context(self, sample_task):
        todo_list = [sample_task]
        visual = get_visual_todo_list(todo_list, filter="@shop")
        assert "Buy milk" in visual

    def test_filter_by_project(self, sample_task):
        todo_list = [sample_task]
        visual = get_visual_todo_list(todo_list, filter="+groceries")
        assert "Buy milk" in visual

    def test_filter_no_match(self, sample_task):
        todo_list = [sample_task]
        visual = get_visual_todo_list(todo_list, filter="@nonexistent")
        assert "Empty todo list" in visual

    def test_filter_by_keyval(self, sample_task):
        todo_list = [sample_task]
        visual = get_visual_todo_list(todo_list, filter="id:1")
        assert "Buy milk" in visual


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


class TestGetVisualTodoCard:
    """Tests for get_visual_todo_card variations."""

    def test_completed_task_card(self):
        task = TodoTaskModel(
            description="Completed task",
            completed=True,
            priority="A",
        )
        card = get_visual_todo_card(task, [])
        assert "DONE" in card

    def test_doing_task_card(self):
        task = TodoTaskModel(
            description="In progress task",
            completed=False,
            keyval={"duration": "2h"},
        )
        card = get_visual_todo_card(task, [])
        assert "DOING" in card

    def test_task_with_dates(self):
        task = TodoTaskModel(
            description="Task with dates",
            completed=True,
            creation_date=datetime.date(2023, 10, 26),
            completion_date=datetime.date(2023, 10, 27),
        )
        card = get_visual_todo_card(task, [])
        assert "2023-10-26" in card
        assert "2023-10-27" in card


class TestDurationFunctions:
    """Tests for duration parsing edge cases."""

    def test_parse_duration_complex(self):
        assert parse_duration("1w2d3h4m5s") == 604800 + 172800 + 10800 + 240 + 5

    def test_parse_duration_zero(self):
        assert parse_duration("") == 0

    def test_parse_duration_months(self):
        # M = months (2592000 seconds each)
        assert parse_duration("1M") == 2592000

    def test_format_duration_zero(self):
        from zrb.util.todo import _format_duration

        assert _format_duration(0) == "0s"


class TestDateToStr:
    """Tests for _date_to_str function."""

    def test_date_to_str_none(self):
        from zrb.util.todo import _date_to_str

        result = _date_to_str(None)
        assert result == "".ljust(14)

    def test_date_to_str_valid(self):
        from zrb.util.todo import _date_to_str

        result = _date_to_str(datetime.date(2023, 10, 26))
        assert "2023-10-26" in result


class TestGetLineStr:
    """Tests for _get_line_str with different terminal widths."""

    def test_full_width(self):
        from zrb.util.todo import _GAP_WIDTH, _get_line_str

        result = _get_line_str(
            terminal_width=200,
            description_width=50,
            additional_info_width=30,
            priority="(A)",
            completed="[x]",
            completed_at="Completed At  ",
            created_at="Created At     ",
            description="Test task",
            additional_info="+project @context",
        )
        assert "Test task" in result
        assert "(A)" in result

    def test_medium_width(self):
        from zrb.util.todo import _get_line_str

        result = _get_line_str(
            terminal_width=120,
            description_width=50,
            additional_info_width=30,
            priority="(A)",
            completed="[x]",
            completed_at="Completed At  ",
            created_at="Created At     ",
            description="Test task",
            additional_info="+project @context",
        )
        assert "Test task" in result

    def test_narrow_width(self):
        from zrb.util.todo import _get_line_str

        result = _get_line_str(
            terminal_width=30,
            description_width=10,
            additional_info_width=0,
            priority="(A)",
            completed="[x]",
            completed_at="Completed At  ",
            created_at="Created At     ",
            description="Test",
            additional_info="",
        )
        # Narrow width should still show priority
        assert "(A)" in result


class TestVisualTodoLineTruncation:
    """Tests for description truncation in visual todo line."""

    def test_long_description_truncation(self):
        from zrb.util.todo import _MAX_DESCRIPTION_WIDTH, get_visual_todo_line

        long_task = TodoTaskModel(
            description="A" * 100,  # Very long description
            completed=False,
        )
        result = get_visual_todo_line(
            terminal_width=200,
            max_desc_length=70,
            max_additional_info_length=30,
            todo_task=long_task,
        )
        # Should be truncated
        assert "..." in result

    def test_completed_task_styling(self):
        task = TodoTaskModel(
            description="Done task",
            completed=True,
        )
        result = get_visual_todo_line(
            terminal_width=200,
            max_desc_length=70,
            max_additional_info_length=30,
            todo_task=task,
        )
        assert "[x]" in result

    def test_task_with_duration_styling(self):
        task = TodoTaskModel(
            description="In progress task",
            completed=False,
            keyval={"duration": "2h"},
        )
        result = get_visual_todo_line(
            terminal_width=200,
            max_desc_length=70,
            max_additional_info_length=30,
            todo_task=task,
        )
        # Should style with bold yellow for duration
        assert "In progress task" in result


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
