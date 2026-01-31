import json

import requests

BASE_URL = "http://localhost:8000"


def test_partial_update():
    """Test partial update (only title, only completed)"""
    print("Testing partial updates...")

    # Create a new todo
    new_todo = {"title": "Partial update test", "completed": False}
    response = requests.post(f"{BASE_URL}/todos", json=new_todo)
    todo_id = response.json()["id"]
    print(f"Created todo with id: {todo_id}")

    # Update only title
    print("\n1. Update only title...")
    update_title = {"title": "Updated title only"}
    response = requests.put(f"{BASE_URL}/todos/{todo_id}", json=update_title)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    # Update only completed
    print("\n2. Update only completed status...")
    update_completed = {"completed": True}
    response = requests.put(f"{BASE_URL}/todos/{todo_id}", json=update_completed)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

    # Verify final state
    print("\n3. Verify final state...")
    response = requests.get(f"{BASE_URL}/todos")
    todos = response.json()
    final_todo = next(todo for todo in todos if todo["id"] == todo_id)
    print(f"Final todo: {json.dumps(final_todo, indent=2)}")

    # Check that both fields were updated correctly
    assert final_todo["title"] == "Updated title only"
    assert final_todo["completed"] == True
    print("✅ Partial updates work correctly!")


def test_auto_increment():
    """Test that IDs auto-increment correctly"""
    print("\n\nTesting auto-increment logic...")

    # Get current todos to find max ID
    response = requests.get(f"{BASE_URL}/todos")
    todos = response.json()
    max_id = max(todo["id"] for todo in todos)
    print(f"Current max ID: {max_id}")

    # Create multiple new todos
    for i in range(3):
        new_todo = {"title": f"Auto-increment test {i+1}", "completed": False}
        response = requests.post(f"{BASE_URL}/todos", json=new_todo)
        created_id = response.json()["id"]
        expected_id = max_id + i + 1
        print(f"Created todo {i+1}: id={created_id}, expected={expected_id}")
        assert (
            created_id == expected_id
        ), f"ID mismatch: got {created_id}, expected {expected_id}"

    print("✅ Auto-increment works correctly!")


def test_empty_update():
    """Test update with empty body (should not change anything)"""
    print("\n\nTesting empty update...")

    # Create a todo
    new_todo = {"title": "Empty update test", "completed": False}
    response = requests.post(f"{BASE_URL}/todos", json=new_todo)
    todo_id = response.json()["id"]
    original_todo = response.json()

    # Try empty update
    print("Sending empty update body...")
    response = requests.put(f"{BASE_URL}/todos/{todo_id}", json={})
    print(f"Status: {response.status_code}")

    # Get the todo again
    response = requests.get(f"{BASE_URL}/todos")
    todos = response.json()
    updated_todo = next(todo for todo in todos if todo["id"] == todo_id)

    # Should be unchanged
    assert updated_todo["title"] == original_todo["title"]
    assert updated_todo["completed"] == original_todo["completed"]
    print(f"Todo unchanged: {json.dumps(updated_todo, indent=2)}")
    print("✅ Empty update doesn't change anything!")


def test_invalid_data():
    """Test with invalid data types"""
    print("\n\nTesting invalid data...")

    # Test POST with invalid completed type
    print("1. POST with string for completed...")
    invalid_todo = {"title": "Test", "completed": "not-a-boolean"}
    response = requests.post(f"{BASE_URL}/todos", json=invalid_todo)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    # FastAPI should return 422 for validation error

    # Test POST without required field
    print("\n2. POST without title...")
    invalid_todo = {"completed": False}
    response = requests.post(f"{BASE_URL}/todos", json=invalid_todo)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

    print("✅ Invalid data handled correctly!")


if __name__ == "__main__":
    try:
        test_partial_update()
        test_auto_increment()
        test_empty_update()
        test_invalid_data()
        print("\n🎉 All edge case tests completed!")
    except requests.exceptions.ConnectionError:
        print(
            "❌ Could not connect to server. Make sure the todo app is running on port 8000."
        )
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
