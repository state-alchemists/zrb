import datetime

import pytest

from zrb.util.todo.model import TodoTaskModel
from zrb.util.todo.render import (
    date_to_str,
    get_line_str,
    get_visual_todo_card,
    get_visual_todo_line,
    get_visual_todo_list,
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


class TestDateToStr:
    """Tests for date_to_str function."""

    def test_date_to_str_none(self):
        result = date_to_str(None)
        assert result == "".ljust(14)

    def test_date_to_str_valid(self):
        result = date_to_str(datetime.date(2023, 10, 26))
        assert "2023-10-26" in result


class TestGetLineStr:
    """Tests for get_line_str with different terminal widths."""

    def test_full_width(self):
        result = get_line_str(
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
        result = get_line_str(
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
        result = get_line_str(
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
