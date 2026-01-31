import json

import requests

BASE_URL = "http://localhost:8000"


def test_get_todos():
    """Test GET /todos"""
    print("Testing GET /todos...")
    response = requests.get(f"{BASE_URL}/todos")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def test_create_todo():
    """Test POST /todos"""
    print("\nTesting POST /todos...")
    new_todo = {"title": "Test new todo", "completed": False}
    response = requests.post(f"{BASE_URL}/todos", json=new_todo)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 201


def test_update_todo():
    """Test PUT /todos/{id}"""
    print("\nTesting PUT /todos/1...")
    update_data = {"title": "Updated groceries", "completed": True}
    response = requests.put(f"{BASE_URL}/todos/1", json=update_data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


def test_update_nonexistent_todo():
    """Test PUT /todos/{id} with non-existent ID"""
    print("\nTesting PUT /todos/999 (non-existent)...")
    update_data = {"title": "Should not exist"}
    response = requests.put(f"{BASE_URL}/todos/999", json=update_data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    return response.status_code == 404


def test_delete_todo():
    """Test DELETE /todos/{id}"""
    print("\nTesting DELETE /todos/2...")
    response = requests.delete(f"{BASE_URL}/todos/2")
    print(f"Status: {response.status_code}")
    return response.status_code == 204


def test_delete_nonexistent_todo():
    """Test DELETE /todos/{id} with non-existent ID"""
    print("\nTesting DELETE /todos/999 (non-existent)...")
    response = requests.delete(f"{BASE_URL}/todos/999")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    return response.status_code == 404


def test_final_state():
    """Test final state after all operations"""
    print("\nTesting final state (GET /todos)...")
    response = requests.get(f"{BASE_URL}/todos")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200


if __name__ == "__main__":
    # Start by checking if server is running
    try:
        # Run tests
        all_passed = True

        # Get initial todos
        if not test_get_todos():
            all_passed = False

        # Create a new todo
        if not test_create_todo():
            all_passed = False

        # Update existing todo
        if not test_update_todo():
            all_passed = False

        # Try to update non-existent todo
        if not test_update_nonexistent_todo():
            all_passed = False

        # Delete existing todo
        if not test_delete_todo():
            all_passed = False

        # Try to delete non-existent todo
        if not test_delete_nonexistent_todo():
            all_passed = False

        # Check final state
        if not test_final_state():
            all_passed = False

        if all_passed:
            print("\n✅ All tests passed!")
        else:
            print("\n❌ Some tests failed!")

    except requests.exceptions.ConnectionError:
        print(
            "❌ Could not connect to server. Make sure the todo app is running on port 8000."
        )
        print("Run: python todo_app.py")
