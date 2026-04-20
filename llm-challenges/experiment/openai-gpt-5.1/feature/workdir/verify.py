#!/usr/bin/env python3
import os
import sys


def verify():
    print("Verifying Project Management API...")

    sys.path.insert(0, os.getcwd())
    try:
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app, raise_server_exceptions=False)
    except Exception as e:
        print(f"FAIL: Could not import app: {e}")
        print("VERIFICATION_RESULT: FAIL")
        return False

    score = 0
    max_score = 9

    # 1. GET /projects still works
    res = client.get("/projects")
    if res.status_code == 200 and len(res.json()) >= 2:
        print("PASS: GET /projects works")
        score += 1
    else:
        print(f"FAIL: GET /projects returned {res.status_code}")

    # 2. Filter by status
    res = client.get("/tasks?status=done")
    tasks = res.json() if res.status_code == 200 else []
    if res.status_code == 200 and tasks and all(t["status"] == "done" for t in tasks):
        print("PASS: Filter by status works")
        score += 1
    else:
        print(f"FAIL: Filter by status — got {res.status_code}, results: {tasks}")

    # 3. Filter by assigned_to
    res = client.get("/tasks?assigned_to=alice")
    tasks = res.json() if res.status_code == 200 else []
    if res.status_code == 200 and tasks and all(t.get("assigned_to") == "alice" for t in tasks):
        print("PASS: Filter by assigned_to works")
        score += 1
    else:
        print(f"FAIL: Filter by assigned_to — got {res.status_code}")

    # 4. Pagination
    res = client.get("/tasks?page=1&page_size=2")
    tasks = res.json() if res.status_code == 200 else (res.json().get("items", []) if isinstance(res.json(), dict) else [])
    result_count = len(tasks) if isinstance(tasks, list) else 0
    if res.status_code == 200 and 0 < result_count <= 2:
        print(f"PASS: Pagination works (page_size=2 returned {result_count} results)")
        score += 1
    else:
        print(f"FAIL: Pagination — got {res.status_code}, count={result_count}")

    # 5. POST without auth → 401
    res = client.post("/tasks", json={"title": "Unauth", "project_id": 1})
    if res.status_code in [401, 403]:
        print("PASS: POST /tasks requires authentication (401/403)")
        score += 1
    else:
        print(f"FAIL: POST without auth returned {res.status_code} (expected 401/403)")

    # 6. POST with valid auth and valid project_id → success
    res = client.post(
        "/tasks",
        json={"title": "Auth Task", "project_id": 1, "priority": 4},
        headers={"X-API-Key": "dev-key-alice"},
    )
    if res.status_code in [200, 201]:
        new_task = res.json()
        if new_task.get("id") and new_task.get("title") == "Auth Task":
            print("PASS: POST /tasks creates task with auth")
            score += 1
            new_id = new_task["id"]
        else:
            print(f"FAIL: POST /tasks returned unexpected body: {new_task}")
            new_id = None
    else:
        print(f"FAIL: POST /tasks with auth returned {res.status_code}: {res.text[:200]}")
        new_id = None

    # 7. POST with invalid project_id → 404
    res = client.post(
        "/tasks",
        json={"title": "Bad", "project_id": 9999},
        headers={"X-API-Key": "dev-key-alice"},
    )
    if res.status_code == 404:
        print("PASS: POST /tasks with invalid project_id returns 404")
        score += 1
    else:
        print(f"FAIL: Invalid project_id returned {res.status_code} (expected 404)")

    # 8. PUT partial update with auth
    update_id = new_id if new_id else 1
    res = client.put(
        f"/tasks/{update_id}",
        json={"status": "in_progress"},
        headers={"X-API-Key": "dev-key-alice"},
    )
    if res.status_code == 200 and res.json().get("status") == "in_progress":
        print("PASS: PUT /tasks/{id} partial update works")
        score += 1
    else:
        print(f"FAIL: PUT /tasks/{update_id} returned {res.status_code}")

    # 9. DELETE with auth, then verify 404
    delete_id = new_id if new_id else 3
    res = client.delete(f"/tasks/{delete_id}", headers={"X-API-Key": "dev-key-alice"})
    if res.status_code in [200, 204]:
        check = client.get(f"/tasks/{delete_id}")
        if check.status_code == 404:
            print("PASS: DELETE /tasks/{id} removes task")
            score += 1
        else:
            print("FAIL: DELETE succeeded but task still accessible")
    else:
        print(f"FAIL: DELETE /tasks/{delete_id} returned {res.status_code}")

    print(f"\nScore: {score}/{max_score}")
    if score >= 8:
        print("VERIFICATION_RESULT: EXCELLENT")
    elif score >= 6:
        print("VERIFICATION_RESULT: PASS")
    else:
        print(f"FAIL: Score too low ({score}/{max_score})")
        print("VERIFICATION_RESULT: FAIL")
        return False

    return True


if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)
