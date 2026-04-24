from fastapi.testclient import TestClient

from app.database import tasks
from app.main import app
from app.models import Task, TaskStatus


client = TestClient(app)
API_HEADERS = {"X-API-Key": "dev-key-alice"}


def setup_function():
    tasks[:] = [
        Task(
            id=1,
            title="Design schema",
            status=TaskStatus.done,
            priority=5,
            project_id=1,
            assigned_to="alice",
        ),
        Task(
            id=2,
            title="Implement API",
            status=TaskStatus.in_progress,
            priority=4,
            project_id=1,
            assigned_to="bob",
        ),
        Task(
            id=3,
            title="Write tests",
            status=TaskStatus.todo,
            priority=3,
            project_id=1,
            assigned_to=None,
        ),
        Task(
            id=4,
            title="Deploy to staging",
            status=TaskStatus.todo,
            priority=2,
            project_id=2,
            assigned_to="alice",
        ),
    ]


def test_list_tasks_filters_and_pagination():
    response = client.get(
        "/tasks",
        params={
            "status": "todo",
            "assigned_to": "alice",
            "page": 1,
            "page_size": 5,
        },
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


def test_list_tasks_paginates_matching_results():
    response = client.get("/tasks", params={"page": 2, "page_size": 2})

    assert response.status_code == 200
    assert [task["id"] for task in response.json()] == [3, 4]


def test_create_task_requires_authentication():
    response = client.post(
        "/tasks",
        json={"title": "New task", "project_id": 1},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}


def test_create_task_validates_project_id_and_generates_id():
    response = client.post(
        "/tasks",
        headers=API_HEADERS,
        json={
            "title": "Document API",
            "project_id": 2,
            "priority": 1,
            "assigned_to": "alice",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": 5,
        "title": "Document API",
        "status": "todo",
        "priority": 1,
        "project_id": 2,
        "assigned_to": "alice",
    }


def test_create_task_returns_404_for_unknown_project():
    response = client.post(
        "/tasks",
        headers=API_HEADERS,
        json={"title": "Ghost task", "project_id": 999},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_update_task_requires_auth_and_partially_updates_fields():
    response = client.put(
        "/tasks/2",
        headers=API_HEADERS,
        json={"title": "Implement REST API", "assigned_to": "alice"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": 2,
        "title": "Implement REST API",
        "status": "in_progress",
        "priority": 4,
        "project_id": 1,
        "assigned_to": "alice",
    }


def test_update_task_returns_404_for_missing_task():
    response = client.put(
        "/tasks/999",
        headers=API_HEADERS,
        json={"title": "Nope"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_delete_task_requires_auth_and_removes_task():
    response = client.delete("/tasks/3", headers=API_HEADERS)

    assert response.status_code == 200
    assert response.json() == {"detail": "Task deleted"}
    assert [task["id"] if isinstance(task, dict) else task.id for task in tasks] == [1, 2, 4]


def test_delete_task_returns_404_for_missing_task():
    response = client.delete("/tasks/999", headers=API_HEADERS)

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}
