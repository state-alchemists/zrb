"""Validator for the project-management API feature challenge.

Runs every TestClient assertion inside a subprocess so the FastAPI app
module is loaded fresh per trial (no sys.modules collisions across cells).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from zrb_llm_evaluator.models import ValidationCheck, ValidationResult
from zrb_llm_evaluator.protocols import ValidatorProtocol

MAX_SCORE = 9

CHECK_SCRIPT = r"""
import json, sys, traceback
sys.path.insert(0, ".")

try:
    from fastapi.testclient import TestClient
    from app.main import app
except Exception:
    print("__RESULT__" + json.dumps({"import_error": traceback.format_exc()}))
    sys.exit(0)

client = TestClient(app, raise_server_exceptions=False)
checks = []

def record(name, passed, message):
    checks.append({"name": name, "passed": bool(passed), "message": message})

res = client.get("/projects")
record(
    "get_projects",
    res.status_code == 200 and len(res.json()) >= 2,
    f"status={res.status_code}",
)

res = client.get("/tasks?status=done")
tasks = res.json() if res.status_code == 200 else []
record(
    "filter_by_status",
    res.status_code == 200 and tasks and all(t.get("status") == "done" for t in tasks),
    f"status={res.status_code}, n={len(tasks) if isinstance(tasks, list) else 0}",
)

res = client.get("/tasks?assigned_to=alice")
tasks = res.json() if res.status_code == 200 else []
record(
    "filter_by_assigned_to",
    res.status_code == 200 and tasks and all(t.get("assigned_to") == "alice" for t in tasks),
    f"status={res.status_code}",
)

res = client.get("/tasks?page=1&page_size=2")
body = res.json() if res.status_code == 200 else None
if isinstance(body, list):
    n = len(body)
elif isinstance(body, dict):
    n = len(body.get("items", []))
else:
    n = 0
record(
    "pagination",
    res.status_code == 200 and 0 < n <= 2,
    f"status={res.status_code}, n={n}",
)

res = client.post("/tasks", json={"title": "Unauth", "project_id": 1})
record(
    "auth_required_on_post",
    res.status_code in (401, 403),
    f"status={res.status_code}",
)

new_id = None
res = client.post(
    "/tasks",
    json={"title": "Auth Task", "project_id": 1, "priority": 4},
    headers={"X-API-Key": "dev-key-alice"},
)
if res.status_code in (200, 201):
    body = res.json()
    if body.get("id") and body.get("title") == "Auth Task":
        record("post_creates_task", True, f"id={body.get('id')}")
        new_id = body["id"]
    else:
        record("post_creates_task", False, f"unexpected body: {body}")
else:
    record("post_creates_task", False, f"status={res.status_code}: {res.text[:200]}")

res = client.post(
    "/tasks",
    json={"title": "Bad", "project_id": 9999},
    headers={"X-API-Key": "dev-key-alice"},
)
record(
    "invalid_project_id_404",
    res.status_code == 404,
    f"status={res.status_code}",
)

update_id = new_id if new_id else 1
res = client.put(
    f"/tasks/{update_id}",
    json={"status": "in_progress"},
    headers={"X-API-Key": "dev-key-alice"},
)
record(
    "put_partial_update",
    res.status_code == 200 and (res.json() or {}).get("status") == "in_progress",
    f"status={res.status_code}",
)

delete_id = new_id if new_id else 3
res = client.delete(f"/tasks/{delete_id}", headers={"X-API-Key": "dev-key-alice"})
if res.status_code in (200, 204):
    check = client.get(f"/tasks/{delete_id}")
    record(
        "delete_removes_task",
        check.status_code == 404,
        f"delete={res.status_code}, post-get={check.status_code}",
    )
else:
    record("delete_removes_task", False, f"delete status={res.status_code}")

print("__RESULT__" + json.dumps({"checks": checks}))
"""


def _parse_payload(stdout: str) -> dict | None:
    for line in stdout.splitlines():
        if line.startswith("__RESULT__"):
            return json.loads(line[len("__RESULT__"):])
    return None


class FeatureValidator:
    def validate(self, output_dir: Path, log_content: str) -> ValidationResult:
        details: list[ValidationCheck] = []
        proc = subprocess.run(
            [sys.executable, "-c", CHECK_SCRIPT],
            cwd=str(output_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
        payload = _parse_payload(proc.stdout)
        if payload is None:
            details.append(
                ValidationCheck(
                    name="check_subprocess",
                    passed=False,
                    message=f"No structured output. stderr: {proc.stderr[:500]}",
                )
            )
            return ValidationResult(status="FAIL", score=0.0, details=details)

        if "import_error" in payload:
            details.append(
                ValidationCheck(
                    name="import",
                    passed=False,
                    message=payload["import_error"][:500],
                )
            )
            return ValidationResult(status="FAIL", score=0.0, details=details)

        for c in payload["checks"]:
            details.append(
                ValidationCheck(
                    name=c["name"],
                    passed=c["passed"],
                    message=c["message"],
                )
            )

        score = sum(1 for c in payload["checks"] if c["passed"])
        normalized = score / MAX_SCORE
        if score >= 8:
            status = "EXCELLENT"
        elif score >= 6:
            status = "PASS"
        else:
            status = "FAIL"
        return ValidationResult(status=status, score=normalized, details=details)


validator = FeatureValidator()
