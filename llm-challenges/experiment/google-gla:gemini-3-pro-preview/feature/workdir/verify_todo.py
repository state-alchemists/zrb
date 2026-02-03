from fastapi.testclient import TestClient
from todo_app import app

client = TestClient(app)


def test_crud():
    # 1. GET initial
    response = client.get("/todos")
    assert response.status_code == 200
    assert len(response.json()) == 2
    print("GET /todos passed")

    # 2. POST create
    new_todo = {"title": "Test Todo", "completed": False}
    response = client.post("/todos", json=new_todo)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Todo"
    assert data["id"] == 3
    print("POST /todos passed")

    # 3. PUT update
    update_data = {"completed": True}
    response = client.put("/todos/3", json=update_data)
    assert response.status_code == 200
    assert response.json()["completed"] is True
    assert response.json()["title"] == "Test Todo"  # Should preserve other fields
    print("PUT /todos passed")

    # 4. DELETE
    response = client.delete("/todos/3")
    assert response.status_code == 204
    print("DELETE /todos passed")

    # 5. Verify DELETE
    response = client.get("/todos")
    assert len(response.json()) == 2
    ids = [item["id"] for item in response.json()]
    assert 3 not in ids
    print("Verify DELETE passed")

    # 6. Test 404
    response = client.delete("/todos/999")
    assert response.status_code == 404
    print("404 check passed")


if __name__ == "__main__":
    test_crud()
