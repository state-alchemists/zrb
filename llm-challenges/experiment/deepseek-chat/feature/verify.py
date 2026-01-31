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
        return False

    # Read the file to check for implementations
    with open("todo_app.py", "r") as f:
        content = f.read()

    # Check for required endpoints
    checks = []

    # Check for POST endpoint
    if "@app.post" in content or "@app.route" in content and "POST" in content:
        checks.append(("POST endpoint", True))
    else:
        checks.append(("POST endpoint", False))

    # Check for PUT endpoint
    if "@app.put" in content or "@app.route" in content and "PUT" in content:
        checks.append(("PUT endpoint", True))
    else:
        checks.append(("PUT endpoint", False))

    # Check for DELETE endpoint
    if "@app.delete" in content or "@app.route" in content and "DELETE" in content:
        checks.append(("DELETE endpoint", True))
    else:
        checks.append(("DELETE endpoint", False))

    # Check for ID generation logic
    if "max(" in content or "max_id" in content or "len(" in content:
        checks.append(("ID generation logic", True))
    else:
        checks.append(("ID generation logic", False))

    # Check for 404 handling
    if (
        "404" in content
        or "HTTPException" in content
        or "status.HTTP_404_NOT_FOUND" in content
    ):
        checks.append(("404 handling", True))
    else:
        checks.append(("404 handling", False))

    # Try to run the app and test endpoints
    print("Testing FastAPI application...")

    # Start the server in background
    import threading

    import uvicorn

    def run_server():
        try:
            # Import and run the app
            import importlib.util

            spec = importlib.util.spec_from_file_location("todo_app", "todo_app.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Run uvicorn
            import uvicorn

            uvicorn.run(module.app, host="127.0.0.1", port=8001, log_level="error")
        except Exception as e:
            print(f"Server error: {e}")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Give server time to start
    time.sleep(3)

    # Test endpoints
    base_url = "http://127.0.0.1:8001"

    try:
        # Test GET /todos
        response = requests.get(f"{base_url}/todos", timeout=5)
        if response.status_code == 200:
            checks.append(("GET /todos works", True))
        else:
            checks.append(("GET /todos works", False))

        # Test POST /todos
        new_todo = {"title": "Test todo"}
        response = requests.post(f"{base_url}/todos", json=new_todo, timeout=5)
        if response.status_code in [200, 201]:
            checks.append(("POST /todos works", True))
            new_id = response.json().get("id")
        else:
            checks.append(("POST /todos works", False))
            new_id = None

        if new_id:
            # Test PUT /todos/{id}
            update_data = {"title": "Updated todo", "completed": True}
            response = requests.put(
                f"{base_url}/todos/{new_id}", json=update_data, timeout=5
            )
            if response.status_code == 200:
                checks.append(("PUT /todos/{id} works", True))
            else:
                checks.append(("PUT /todos/{id} works", False))

            # Test DELETE /todos/{id}
            response = requests.delete(f"{base_url}/todos/{new_id}", timeout=5)
            if response.status_code in [200, 204]:
                checks.append(("DELETE /todos/{id} works", True))
            else:
                checks.append(("DELETE /todos/{id} works", False))

            # Test 404 for non-existent item
            response = requests.put(
                f"{base_url}/todos/9999", json=update_data, timeout=5
            )
            if response.status_code == 404:
                checks.append(("PUT returns 404 for non-existent", True))
            else:
                checks.append(("PUT returns 404 for non-existent", False))

    except Exception as e:
        print(f"API test error: {e}")
        checks.append(("API tests", False))

    # Print results
    all_passed = True
    for check_name, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"{status}: {check_name}")
        if not passed:
            all_passed = False

    return all_passed


if __name__ == "__main__":
    success = verify_feature()
    sys.exit(0 if success else 1)
