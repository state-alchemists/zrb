#!/usr/bin/env python3
import os
import sys
from fastapi.testclient import TestClient

def verify():
    print("Verifying Modular Todo App...")
    
    try:
        # We need to be in the right directory for relative imports to work
        sys.path.append(os.getcwd())
        from app.main import app
        client = TestClient(app)
    except Exception as e:
        print(f"FAIL: Could not import app: {e}")
        return False

    try:
        # 1. Test List
        res = client.get("/todos")
        if res.status_code != 200:
            print(f"FAIL: GET /todos failed with {res.status_code}")
            return False
            
        # 2. Test Create
        res = client.post("/todos", json={"title": "New Task"})
        if res.status_code not in [200, 201]:
            print(f"FAIL: POST /todos failed with {res.status_code}")
            return False
        new_todo = res.json()
        new_id = new_todo.get("id")
        if new_id is None:
            print("FAIL: POST /todos did not return an ID")
            return False
        
        # 3. Test Update
        res = client.put(f"/todos/{new_id}", json={"title": "Updated Task", "completed": True})
        if res.status_code != 200:
            print(f"FAIL: PUT /todos/{new_id} failed with {res.status_code}")
            return False
            
        # 4. Test Delete
        res = client.delete(f"/todos/{new_id}")
        if res.status_code not in [200, 204]:
            print(f"FAIL: DELETE /todos/{new_id} failed with {res.status_code}")
            return False
            
        print("PASS: All CRUD operations verified")
        print("VERIFICATION_RESULT: EXCELLENT")
        return True

    except Exception as e:
        print(f"FAIL: Test execution error: {e}")
        return False

if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)
