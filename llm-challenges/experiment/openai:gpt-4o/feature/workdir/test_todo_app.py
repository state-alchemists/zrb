from fastapi.testclient import TestClient
from todo_app import TodoItem, app, db

client = TestClient(app)


def setup_function(function):
    """This function runs before each test, resetting the database."""
    global db
    db.clear()
    db.extend(
        [
            TodoItem(id=1, title="Buy groceries"),
            TodoItem(id=2, title="Walk the dog"),
        ]
    )


def test_create_todo():
    response = client.post("/todos", json={"title": "Read a book", "completed": False})
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Read a book"
    assert data["completed"] is False


def test_update_todo():
    response = client.put(
        "/todos/2", json={"title": "Walk the cat", "completed": False}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Walk the cat"


def test_delete_todo():
    response = client.delete("/todos/1")
    assert response.status_code == 204

    response_get = client.get("/todos")
    assert len(response_get.json()) == 1  # Initially 2, now 1 after deletion
    assert response_get.json()[0]["id"] != 1
