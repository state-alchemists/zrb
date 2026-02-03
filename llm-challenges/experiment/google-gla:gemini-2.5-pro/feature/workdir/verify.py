#!/usr/bin/env python3
import os
import subprocess
import sys
import time

import requests


def verify_feature():
    """Verify the FastAPI todo app challenge."""

    # Check if todo_app.py exists
    if not os.path.exists("todo_app.py"):
        print("FAIL: todo_app.py not found")
        print("VERIFICATION_RESULT: FAIL")
        return False

    # Read the file to check for implementations
    with open("todo_app.py", "r") as f:
        content = f.read()

    # Try to run the app and test endpoints
    print("Testing FastAPI application...")

    # Start the server in background
    import threading

    import uvicorn

    server_process = None
    server_error = False

    def run_server():
        nonlocal server_error
        try:
            # Import and run the app
            import importlib.util

            spec = importlib.util.spec_from_file_location("todo_app", "todo_app.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Run uvicorn
            import uvicorn

            uvicorn.run(module.app, host="localhost", port=8001, log_level="error")
        except Exception as e:
            print(f"Server error: {e}")
            server_error = True

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Give server time to start
    time.sleep(3)

    if server_error:
        print("FAIL: Server failed to start")
        print("VERIFICATION_RESULT: FAIL")
        return False

    # Test endpoints
    base_url = "http://localhost:8001"
    checks = []

    happy_path_score = 0
    edge_case_score = 0

    try:
        # Test GET /todos
        try:
            response = requests.get(f"{base_url}/todos", timeout=5)
            if response.status_code == 200:
                checks.append(("GET /todos works", True))
                happy_path_score += 1
            else:
                checks.append(("GET /todos works", False))
        except requests.exceptions.ConnectionError:
            print("FAIL: Could not connect to server")
            print("VERIFICATION_RESULT: FAIL")
            return False

        # Test POST /todos
        new_todo = {"title": "Test todo", "id": 0}  # ID should be ignored/generated
        response = requests.post(f"{base_url}/todos", json=new_todo, timeout=5)
        if response.status_code in [200, 201]:
            checks.append(("POST /todos works", True))
            happy_path_score += 1
            new_id = response.json().get("id")
        else:
            checks.append(("POST /todos works", False))
            new_id = None

        if new_id:
            # Test PUT /todos/{id}
            update_data = {"title": "Updated todo", "completed": True, "id": new_id}
            response = requests.put(
                f"{base_url}/todos/{new_id}", json=update_data, timeout=5
            )
            if response.status_code == 200:
                checks.append(("PUT /todos/{id} works", True))
                happy_path_score += 1
            else:
                checks.append(("PUT /todos/{id} works", False))

            # Test DELETE /todos/{id}
            response = requests.delete(f"{base_url}/todos/{new_id}", timeout=5)
            if response.status_code in [200, 204]:
                checks.append(("DELETE /todos/{id} works", True))
                happy_path_score += 1
            else:
                checks.append(("DELETE /todos/{id} works", False))

            # Test 404 for non-existent item (Edge Case)
            response = requests.put(
                f"{base_url}/todos/9999", json=update_data, timeout=5
            )
            if response.status_code == 404:
                checks.append(("PUT returns 404 for non-existent", True))
                edge_case_score += 1
            else:
                checks.append(("PUT returns 404 for non-existent", False))

    except Exception as e:
        print(f"API test error: {e}")
        checks.append(("API tests", False))

    # Print results
    for check_name, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {check_name}")

    # Determine status
    # 4 Happy path tests: GET, POST, PUT, DELETE
    if happy_path_score == 4:
        if edge_case_score == 1:
            print("VERIFICATION_RESULT: EXCELLENT")
        else:
            print("VERIFICATION_RESULT: PASS")  # Works but missing error handling
    elif happy_path_score >= 3:
        # Missing one endpoint is arguably a fail for "complete CRUD",
        # but let's say it's a FAIL for this challenge as completeness is key.
        print("VERIFICATION_RESULT: FAIL")
        return False
    else:
        print("VERIFICATION_RESULT: FAIL")
        return False

    return True


if __name__ == "__main__":
    success = verify_feature()
    sys.exit(0 if success else 1)
