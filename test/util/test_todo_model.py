import datetime

import pytest
from zrb.util.todo_model import TodoTaskModel


def test_todo_task_model_valid_creation():
    task = TodoTaskModel(
        description="Test task",
        priority="A",
        completed=False,
        projects=["proj1"],
        contexts=["ctx1"],
        keyval={"due": "2024-01-01"},
        creation_date=datetime.date(2023, 1, 1),
        completion_date=datetime.date(2023, 1, 2),
    )
    assert task.description == "Test task"
    assert task.priority == "A"
    assert not task.completed
    assert task.projects == ["proj1"]
    assert task.contexts == ["ctx1"]
    assert task.keyval == {"due": "2024-01-01"}
    assert task.creation_date == datetime.date(2023, 1, 1)
    assert task.completion_date == datetime.date(2023, 1, 2)


def test_todo_task_model_invalid_priority():
    with pytest.raises(ValueError, match="Invalid priority format"):
        TodoTaskModel(description="Test task", priority="invalid")


def test_todo_task_model_completion_date_without_creation_date():
    with pytest.raises(
        ValueError, match="creation_date must be specified if completion_date is set."
    ):
        TodoTaskModel(
            description="Test task", completion_date=datetime.date(2023, 1, 2)
        )


def test_todo_task_model_get_additional_info_length():
    task = TodoTaskModel(
        description="Test task",
        projects=["proj1", "proj2"],
        contexts=["ctx1"],
        keyval={"due": "2024-01-01"},
    )
    expected_length = len("@proj1, @proj2, +ctx1, due:2024-01-01")
    assert task.get_additional_info_length() == expected_length


def test_todo_task_model_get_additional_info_length_empty():
    task = TodoTaskModel(description="Test task")
    assert task.get_additional_info_length() == 0
