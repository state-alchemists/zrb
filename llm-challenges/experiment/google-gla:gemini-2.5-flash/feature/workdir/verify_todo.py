import asyncio
import time

import httpx

BASE_URL = "http://localhost:8000/todos"


async def verify_todos():
    print("Starting verification...")

    # Wait for the server to be ready
    for _ in range(5):
        try:
            response = await httpx.get(BASE_URL)
            if response.status_code == 200:
                print("Server is ready.")
                break
        except httpx.ConnectError:
            print("Waiting for server...")
            await asyncio.sleep(1)
    else:
        print("Server did not become ready in time.")
        exit(1)

    # 1. GET /todos - Initial check
    response = await httpx.get(BASE_URL)
    assert (
        response.status_code == 200
    ), f"GET /todos failed with status {response.status_code}"
    initial_todos = response.json()
    print(f"Initial todos: {initial_todos}")
    assert len(initial_todos) == 2, "Expected 2 initial todo items"

    # 2. POST /todos - Create a new item
    new_todo_data = {"title": "Learn FastAPI", "completed": False}
    response = await httpx.post(BASE_URL, json=new_todo_data)
    assert (
        response.status_code == 201
    ), f"POST /todos failed with status {response.status_code}"
    created_todo = response.json()
    print(f"Created todo: {created_todo}")
    assert created_todo["title"] == "Learn FastAPI"
    assert created_todo["completed"] is False
    assert "id" in created_todo
    created_id = created_todo["id"]

    # 3. GET /todos - Verify new item is added
    response = await httpx.get(BASE_URL)
    assert (
        response.status_code == 200
    ), f"GET /todos failed after POST with status {response.status_code}"
    todos_after_post = response.json()
    print(f"Todos after POST: {todos_after_post}")
    assert len(todos_after_post) == 3, "Expected 3 todo items after POST"
    assert any(todo["id"] == created_id for todo in todos_after_post)

    # 4. PUT /todos/{item_id} - Update an existing item
    updated_todo_data = {"title": "Master FastAPI", "completed": True}
    response = await httpx.put(f"{BASE_URL}/{created_id}", json=updated_todo_data)
    assert (
        response.status_code == 200
    ), f"PUT /todos/{created_id} failed with status {response.status_code}"
    updated_todo = response.json()
    print(f"Updated todo: {updated_todo}")
    assert updated_todo["id"] == created_id
    assert updated_todo["title"] == "Master FastAPI"
    assert updated_todo["completed"] is True

    # 5. GET /todos - Verify item is updated
    response = await httpx.get(f"{BASE_URL}/{created_id}")
    assert (
        response.status_code == 200
    ), f"GET /todos/{created_id} failed after PUT with status {response.status_code}"
    fetched_updated_todo = response.json()
    assert fetched_updated_todo["title"] == "Master FastAPI"
    assert fetched_updated_todo["completed"] is True

    # 6. DELETE /todos/{item_id} - Delete an item
    response = await httpx.delete(f"{BASE_URL}/{created_id}")
    assert (
        response.status_code == 204
    ), f"DELETE /todos/{created_id} failed with status {response.status_code}"
    print(f"Deleted todo with ID: {created_id}")

    # 7. GET /todos - Verify item is deleted
    response = await httpx.get(BASE_URL)
    assert (
        response.status_code == 200
    ), f"GET /todos failed after DELETE with status {response.status_code}"
    todos_after_delete = response.json()
    print(f"Todos after DELETE: {todos_after_delete}")
    assert len(todos_after_delete) == 2, "Expected 2 todo items after DELETE"
    assert not any(todo["id"] == created_id for todo in todos_after_delete)

    # 8. DELETE /todos/{item_id} - Try to delete a non-existent item (expect 404)
    response = await httpx.delete(f"{BASE_URL}/{created_id}")
    assert (
        response.status_code == 404
    ), f"DELETE non-existent todo did not return 404, got {response.status_code}"
    print("Attempted to delete non-existent todo, received 404 as expected.")

    print("All CRUD operations verified successfully!")


if __name__ == "__main__":
    asyncio.run(verify_todos())
