from copy import deepcopy

from fastapi.testclient import TestClient

from app import database
from app.main import app

client = TestClient(app)

ORIGINAL_PROJECTS = deepcopy(database.projects)
ORIGINAL_TASKS = deepcopy(database.tasks)


def setup_function():
    database.projects[:] = deepcopy(ORIGINAL_PROJECTS)
    database.tasks[:] = deepcopy(ORIGINAL_TASKS)


def test_should_return_401_when_api_key_is_missing():
    response = client.post(
        "/tasks",
        json={"title": "New task", "project_id": 1},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


def test_should_filter_tasks_when_query_params_are_provided():
    response = client.get(
        "/tasks",
        params={"status": "todo", "assigned_to": "alice"},
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


def test_should_create_task_when_authenticated_and_project_exists():
    response = client.post(
        "/tasks",
        headers={"X-API-Key": "dev-key-alice"},
        json={
            "title": "Document API",
            "status": "todo",
            "priority": 1,
            "project_id": 1,
            "assigned_to": "alice",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": 5,
        "title": "Document API",
        "status": "todo",
        "priority": 1,
        "project_id": 1,
        "assigned_to": "alice",
    }


def test_should_return_404_when_creating_task_for_missing_project():
    response = client.post(
        "/tasks",
        headers={"X-API-Key": "dev-key-alice"},
        json={"title": "Ghost", "project_id": 999},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_should_partially_update_task_when_authenticated():
    response = client.put(
        "/tasks/2",
        headers={"X-API-Key": "dev-key-bob"},
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


def test_should_return_404_when_updating_missing_task():
    response = client.put(
        "/tasks/999",
        headers={"X-API-Key": "dev-key-bob"},
        json={"title": "Missing"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_should_delete_task_when_authenticated():
    response = client.delete(
        "/tasks/4",
        headers={"X-API-Key": "dev-key-alice"},
    )

    assert response.status_code == 200
    assert response.json() == {"detail": "Task deleted"}

    get_response = client.get("/tasks/4")
    assert get_response.status_code == 404


def test_should_return_404_when_deleting_missing_task():
    response = client.delete(
        "/tasks/999",
        headers={"X-API-Key": "dev-key-alice"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}
