"""Validator for the bug-fix challenge.

Runs the job-queue simulation in a fresh subprocess so async loops and
module state never leak between trials.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from zrb_llm_evaluator.models import ValidationCheck, ValidationResult
from zrb_llm_evaluator.protocols import ValidatorProtocol

REQUIRED_FILES = ("job_queue.py", "worker.py")
RUNS = 5

# Executed by a subprocess in the trial's working directory.
# Prints a single JSON line prefixed with __RESULT__ that the validator
# parses. A non-zero exit means a hard import / runtime error.
SIMULATION_SCRIPT = r"""
import asyncio, json, sys, traceback
sys.path.insert(0, ".")

try:
    from job_queue import JobQueue
    from worker import process_job
except Exception:
    print("__RESULT__" + json.dumps({"import_error": traceback.format_exc()}))
    sys.exit(0)

with open("job_queue.py") as f: queue_src = f.read()
with open("worker.py") as f: worker_src = f.read()
has_lock = "Lock" in queue_src or "Lock" in worker_src

async def run_simulation():
    q = JobQueue(max_retries=2)
    for i in range(10):
        q.enqueue({"name": f"task_{i}", "raise_error": False})
    q.enqueue({"name": "bad_1", "raise_error": True})
    q.enqueue({"name": "bad_2", "raise_error": True})
    workers = [process_job(q, i) for i in range(5)]
    await asyncio.gather(*workers)
    jobs = q.all_jobs
    done = sum(1 for j in jobs.values() if j["status"] == "done")
    failed = sum(1 for j in jobs.values() if j["status"] == "failed")
    stuck = sum(1 for j in jobs.values() if j["status"] == "processing")
    return done, failed, stuck

runs = []
for _ in range(__RUNS__):
    try:
        runs.append(list(asyncio.run(run_simulation())))
    except Exception:
        runs.append({"error": traceback.format_exc()})

print("__RESULT__" + json.dumps({"runs": runs, "has_lock": has_lock}))
""".replace("__RUNS__", str(RUNS))


def _missing_files(output_dir: Path) -> list[str]:
    return [f for f in REQUIRED_FILES if not (output_dir / f).is_file()]


def _parse_payload(stdout: str) -> dict | None:
    for line in stdout.splitlines():
        if line.startswith("__RESULT__"):
            return json.loads(line[len("__RESULT__"):])
    return None


class BugFixValidator:
    def validate(self, output_dir: Path, log_content: str) -> ValidationResult:
        details: list[ValidationCheck] = []

        missing = _missing_files(output_dir)
        if missing:
            details.append(
                ValidationCheck(
                    name="required_files",
                    passed=False,
                    message=f"Missing files: {', '.join(missing)}",
                )
            )
            return ValidationResult(status="FAIL", score=0.0, details=details)

        proc = subprocess.run(
            [sys.executable, "-c", SIMULATION_SCRIPT],
            cwd=str(output_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
        payload = _parse_payload(proc.stdout)
        if payload is None:
            details.append(
                ValidationCheck(
                    name="simulation_subprocess",
                    passed=False,
                    message=f"Subprocess produced no result. stderr: {proc.stderr[:500]}",
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

        passes = 0
        for idx, run in enumerate(payload["runs"], start=1):
            if isinstance(run, dict) and "error" in run:
                details.append(
                    ValidationCheck(
                        name=f"run_{idx}",
                        passed=False,
                        message=run["error"][:400],
                    )
                )
                continue
            done, failed, stuck = run
            ok = done == 10 and failed == 2 and stuck == 0
            if ok:
                passes += 1
            details.append(
                ValidationCheck(
                    name=f"run_{idx}",
                    passed=ok,
                    message=f"done={done}, failed={failed}, stuck={stuck}",
                )
            )

        all_passed = passes == RUNS
        has_lock = bool(payload.get("has_lock"))
        details.append(
            ValidationCheck(
                name="concurrency_primitive",
                passed=has_lock,
                message="Lock found in source" if has_lock else "No Lock primitive detected",
            )
        )

        if not all_passed:
            return ValidationResult(
                status="FAIL",
                score=passes / RUNS,
                details=details,
            )
        if has_lock:
            return ValidationResult(status="EXCELLENT", score=1.0, details=details)
        return ValidationResult(status="PASS", score=0.85, details=details)


validator = BugFixValidator()
