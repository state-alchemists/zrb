#!/usr/bin/env python3
"""Test script to verify Todo API endpoints"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_get_todos():
    """Test GET /todos"""
    print("Testing GET /todos...")
    response = requests.get(f"{BASE_URL}/todos")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_get_todo(todo_id):
    """Test GET /todos/{todo_id}"""
    print(f"Testing GET /todos/{todo_id}...")
    response = requests.get(f"{BASE_URL}/todos/{todo_id}")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"Response: {response.text}")
    print()

def test_create_todo():
    """Test POST /todos"""
    print("Testing POST /todos...")
    new_todo = {
        "title": "Test new todo",
        "completed": False
    }
    response = requests.post(f"{BASE_URL}/todos", json=new_todo)
    print(f"Status: {response.status_code}")
    if response.status_code == 201:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()["id"]
    else:
        print(f"Response: {response.text}")
    print()
    return None

def test_update_todo(todo_id):
    """Test PUT /todos/{todo_id}"""
    print(f"Testing PUT /todos/{todo_id}...")
    updated_todo = {
        "title": "Updated todo title",
        "completed": True
    }
    response = requests.put(f"{BASE_URL}/todos/{todo_id}", json=updated_todo)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"Response: {response.text}")
    print()

def test_delete_todo(todo_id):
    """Test DELETE /todos/{todo_id}"""
    print(f"Testing DELETE /todos/{todo_id}...")
    response = requests.delete(f"{BASE_URL}/todos/{todo_id}")
    print(f"Status: {response.status_code}")
    print(f"Response: {'No content' if response.status_code == 204 else response.text}")
    print()

if __name__ == "__main__":
    print("=== Todo API Test Suite ===\n")
    
    # First, check existing todos
    test_get_todos()
    
    # Test getting existing todo
    test_get_todo(1)
    
    # Test getting non-existent todo
    test_get_todo(999)
    
    # Test creating a new todo
    new_id = test_create_todo()
    
    if new_id:
        # Test updating the new todo
        test_update_todo(new_id)
        
        # Test deleting the new todo
        test_delete_todo(new_id)
        
        # Verify deletion
        test_get_todo(new_id)
    
    print("=== Test Complete ===")