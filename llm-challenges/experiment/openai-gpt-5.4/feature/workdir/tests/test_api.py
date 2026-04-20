from fastapi.testclient import TestClient

from app.main import app
from app.database import tasks
from app.models import Task, TaskStatus


client = TestClient(app)
API_KEY_HEADERS = {"X-API-Key": "dev-key-alice"}
INITIAL_TASKS = [
    Task(id=1, title="Design schema", status=TaskStatus.done, priority=5, project_id=1, assigned_to="alice"),
    Task(id=2, title="Implement API", status=TaskStatus.in_progress, priority=4, project_id=1, assigned_to="bob"),
    Task(id=3, title="Write tests", status=TaskStatus.todo, priority=3, project_id=1),
    Task(id=4, title="Deploy to staging", status=TaskStatus.todo, priority=2, project_id=2, assigned_to="alice"),
]


def setup_function():
    tasks[:] = [task.model_copy(deep=True) for task in INITIAL_TASKS]


def test_should_filter_tasks_when_status_priority_and_assigned_to_are_provided():
    response = client.get(
        "/tasks",
        params={"status": "todo", "priority": 2, "assigned_to": "alice"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 4,
            "title": "Deploy to staging",
            "status": "todo",
            "priority": 2,
            "project_id": 2,
            "assigned_to": "alice",
        }
    ]


def test_should_paginate_filtered_tasks_when_page_and_page_size_are_provided():
    response = client.get(
        "/tasks",
        params={"assigned_to": "alice", "page": 2, "page_size": 1},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 4,
            "title": "Deploy to staging",
            "status": "todo",
            "priority": 2,
            "project_id": 2,
            "assigned_to": "alice",
        }
    ]


def test_should_reject_task_creation_when_api_key_is_missing():
    response = client.post(
        "/tasks",
        json={"title": "Document API", "project_id": 1},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


def test_should_create_task_when_authenticated_and_project_exists():
    response = client.post(
        "/tasks",
        headers=API_KEY_HEADERS,
        json={
            "title": "Document API",
            "status": "todo",
            "priority": 1,
            "project_id": 2,
            "assigned_to": "bob",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": 5,
        "title": "Document API",
        "status": "todo",
        "priority": 1,
        "project_id": 2,
        "assigned_to": "bob",
    }


def test_should_return_not_found_when_creating_task_for_unknown_project():
    response = client.post(
        "/tasks",
        headers=API_KEY_HEADERS,
        json={"title": "Ghost task", "project_id": 999},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_should_partially_update_task_when_authenticated():
    response = client.put(
        "/tasks/2",
        headers=API_KEY_HEADERS,
        json={"status": "done", "assigned_to": "alice"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": 2,
        "title": "Implement API",
        "status": "done",
        "priority": 4,
        "project_id": 1,
        "assigned_to": "alice",
    }


def test_should_return_not_found_when_updating_unknown_task():
    response = client.put(
        "/tasks/999",
        headers=API_KEY_HEADERS,
        json={"title": "Missing"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_should_delete_task_when_authenticated():
    response = client.delete("/tasks/3", headers=API_KEY_HEADERS)

    assert response.status_code == 200
    assert response.json() == {"detail": "Task deleted"}
    assert [task.id for task in tasks] == [1, 2, 4]


def test_should_return_not_found_when_deleting_unknown_task():
    response = client.delete("/tasks/999", headers=API_KEY_HEADERS)

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}
