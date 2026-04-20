from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_auth():
    response = client.post("/tasks", json={"title": "Test", "project_id": 1})
    assert response.status_code == 401

    response = client.post("/tasks", json={"title": "Test", "project_id": 1}, headers={"X-API-Key": "invalid"})
    assert response.status_code == 401

def test_tasks_filter_and_pagination():
    response = client.get("/tasks?status=todo")
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert all(t["status"] == "todo" for t in response.json())

    response = client.get("/tasks?priority=5")
    assert len(response.json()) == 1

    response = client.get("/tasks?page_size=2")
    assert len(response.json()) == 2

def test_create_task():
    response = client.post("/tasks", json={"title": "New Task", "project_id": 999}, headers={"X-API-Key": "dev-key-alice"})
    assert response.status_code == 404

    response = client.post("/tasks", json={"title": "New Task", "project_id": 1}, headers={"X-API-Key": "dev-key-alice"})
    assert response.status_code == 200
    task = response.json()
    assert task["id"] == 5
    assert task["title"] == "New Task"
    
def test_update_task():
    response = client.put("/tasks/1", json={"status": "in_progress"}, headers={"X-API-Key": "dev-key-alice"})
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"

def test_delete_task():
    response = client.delete("/tasks/1", headers={"X-API-Key": "dev-key-alice"})
    assert response.status_code == 200

    response = client.get("/tasks/1")
    assert response.status_code == 404

test_auth()
test_tasks_filter_and_pagination()
test_create_task()
test_update_task()
test_delete_task()
print("All tests passed!")
