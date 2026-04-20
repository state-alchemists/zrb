from fastapi.testclient import TestClient
from app.main import app
from app.database import tasks, projects, VALID_API_KEYS
import pytest

client = TestClient(app)

def test_auth_required():
    # POST /tasks
    response = client.post("/tasks", json={"title": "Test", "project_id": 1})
    assert response.status_code == 401
    
    # PUT /tasks/1
    response = client.put("/tasks/1", json={"title": "Updated"})
    assert response.status_code == 401
    
    # DELETE /tasks/1
    response = client.delete("/tasks/1")
    assert response.status_code == 401

def test_auth_invalid_key():
    headers = {"X-API-Key": "invalid"}
    response = client.post("/tasks", json={"title": "Test", "project_id": 1}, headers=headers)
    assert response.status_code == 401

def test_list_tasks_filtering_and_pagination():
    # Setup: Ensure we know what's in the database
    # tasks: id 1 (done, p5, proj1, alice), 2 (in_progress, p4, proj1, bob), 3 (todo, p3, proj1), 4 (todo, p2, proj2, alice)
    
    # Filter by status
    response = client.get("/tasks?status=todo")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(t["status"] == "todo" for t in data)
    
    # Filter by priority
    response = client.get("/tasks?priority=4")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == 2
    
    # Pagination
    response = client.get("/tasks?page=1&page_size=2")
    assert response.status_code == 200
    assert len(response.json()) == 2
    
    response = client.get("/tasks?page=2&page_size=2")
    assert response.status_code == 200
    assert len(response.json()) == 2

def test_create_task():
    headers = {"X-API-Key": "dev-key-alice"}
    payload = {"title": "New Task", "project_id": 1, "status": "todo"}
    response = client.post("/tasks", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New Task"
    assert data["id"] == 5 # Next ID after 4
    assert data["project_id"] == 1

def test_create_task_invalid_project():
    headers = {"X-API-Key": "dev-key-alice"}
    payload = {"title": "New Task", "project_id": 999}
    response = client.post("/tasks", json=payload, headers=headers)
    assert response.status_code == 404

def test_update_task():
    headers = {"X-API-Key": "dev-key-alice"}
    payload = {"status": "done", "priority": 1}
    response = client.put("/tasks/3", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "done"
    assert data["priority"] == 1
    assert data["title"] == "Write tests" # Unchanged

def test_delete_task():
    headers = {"X-API-Key": "dev-key-alice"}
    response = client.delete("/tasks/1", headers=headers)
    assert response.status_code == 200
    
    response = client.get("/tasks/1")
    assert response.status_code == 404
