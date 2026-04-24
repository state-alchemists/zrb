import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import tasks, projects, VALID_API_KEYS

client = TestClient(app)

def test_auth():
    # Test missing key
    response = client.post("/tasks", json={"title": "Test", "project_id": 1})
    assert response.status_code == 401
    
    # Test invalid key
    response = client.post("/tasks", json={"title": "Test", "project_id": 1}, headers={"X-API-Key": "invalid"})
    assert response.status_code == 401
    
    # Test valid key
    response = client.post("/tasks", json={"title": "Test", "project_id": 1}, headers={"X-API-Key": "dev-key-alice"})
    assert response.status_code == 200

def test_list_tasks_filtering():
    # All tasks (assuming test_auth didn't mess up too much, but it added 1 task)
    response = client.get("/tasks")
    # Initial 4 + 1 from test_auth
    assert len(response.json()) >= 4
    
    # Filter by status
    response = client.get("/tasks?status=done")
    assert all(t["status"] == "done" for t in response.json())
    
    # Filter by priority
    response = client.get("/tasks?priority=4")
    assert all(t["priority"] == 4 for t in response.json())

    # Filter by assigned_to
    response = client.get("/tasks?assigned_to=alice")
    assert all(t["assigned_to"] == "alice" for t in response.json())
    
    # Combined filter
    response = client.get("/tasks?assigned_to=alice&status=done")
    assert all(t["assigned_to"] == "alice" and t["status"] == "done" for t in response.json())

def test_pagination():
    response = client.get("/tasks?page=1&page_size=2")
    assert len(response.json()) == 2
    
    response = client.get("/tasks?page=2&page_size=2")
    assert len(response.json()) == 2

def test_create_task():
    initial_count = len(tasks)
    payload = {"title": "New Task", "project_id": 1, "status": "todo", "priority": 1}
    response = client.post("/tasks", json=payload, headers={"X-API-Key": "dev-key-alice"})
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New Task"
    assert data["project_id"] == 1
    assert "id" in data
    assert len(tasks) == initial_count + 1
    
    # Test invalid project_id
    payload = {"title": "New Task", "project_id": 999}
    response = client.post("/tasks", json=payload, headers={"X-API-Key": "dev-key-alice"})
    assert response.status_code == 404

def test_update_task():
    task_id = tasks[0].id
    payload = {"title": "Updated Title", "status": "in_progress"}
    response = client.put(f"/tasks/{task_id}", json=payload, headers={"X-API-Key": "dev-key-alice"})
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["status"] == "in_progress"
    
    # Test 404
    response = client.put("/tasks/9999", json=payload, headers={"X-API-Key": "dev-key-alice"})
    assert response.status_code == 404

def test_delete_task():
    task_id = tasks[0].id
    response = client.delete(f"/tasks/{task_id}", headers={"X-API-Key": "dev-key-alice"})
    assert response.status_code == 200
    
    response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 404
    
    # Test 404
    response = client.delete("/tasks/9999", headers={"X-API-Key": "dev-key-alice"})
    assert response.status_code == 404

if __name__ == "__main__":
    import sys
    retcode = pytest.main([__file__])
    sys.exit(retcode)
