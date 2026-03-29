from fastapi.testclient import TestClient
from app.main import app
from app.database import db

client = TestClient(app)

def test_api():
    # Reset DB
    db.clear()
    
    # 1. POST /todos
    response = client.post("/todos", json={"title": "New Todo"})
    assert response.status_code == 201
    assert response.json() == {"id": 1, "title": "New Todo", "completed": False}
    
    # 2. POST /todos again
    response = client.post("/todos", json={"title": "Second Todo", "completed": True})
    assert response.status_code == 201
    assert response.json() == {"id": 2, "title": "Second Todo", "completed": True}
    
    # 3. PUT /todos/{todo_id}
    response = client.put("/todos/1", json={"title": "Updated Todo", "completed": True})
    assert response.status_code == 200
    assert response.json() == {"id": 1, "title": "Updated Todo", "completed": True}
    
    # 4. GET /todos/{todo_id} verify update
    response = client.get("/todos/1")
    assert response.json() == {"id": 1, "title": "Updated Todo", "completed": True}
    
    # 5. DELETE /todos/{todo_id}
    response = client.delete("/todos/2")
    assert response.status_code == 204
    
    # 6. GET /todos to verify deletion
    response = client.get("/todos")
    assert response.status_code == 200
    assert response.json() == [{"id": 1, "title": "Updated Todo", "completed": True}]
    
    # 7. 404 Tests
    response = client.get("/todos/99")
    assert response.status_code == 404
    response = client.put("/todos/99", json={"title": "Not found"})
    assert response.status_code == 404
    response = client.delete("/todos/99")
    assert response.status_code == 404
    
    print("All tests passed!")

if __name__ == "__main__":
    test_api()
