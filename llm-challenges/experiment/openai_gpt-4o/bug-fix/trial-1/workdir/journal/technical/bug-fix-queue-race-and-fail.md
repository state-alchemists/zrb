---
slug: bug-fix-queue-race-and-fail
---
# Bug Fix: Job Queue Duplicate Processing and Vanishing Failures

**Context:** Bug-fix challenge in llm-challenges — an asyncio-based job queue with concurrent workers.

## Bug 1: Duplicate Processing (TOCTOU Race)

**File:** `challenges/bug-fix/workdir/job_queue.py:30-34`
**Root cause:** `await asyncio.sleep(0.01)` between checking `job["status"] == "pending"` and setting `job["status"] = "processing"`. All workers suspend at the sleep before the claim is recorded, so every worker sees the job as pending and claims it.

**Fix:** Set `"processing"` status *before* the `await` — the status assignment is synchronous, so no other worker can see it as pending after the flag is set.

## Bug 2: Vanishing Failures

**File:** `challenges/bug-fix/workdir/worker.py:15-16`
**Root cause:** The `except` block printed the error but never called `queue.fail()`. Jobs that raised exceptions stayed in `"processing"` status permanently — they disappeared from the queue with no retries and no "failed" state.

**Fix:** Added `queue.fail(job["id"], str(e))` in the except block so the error is recorded and retries are managed by the queue's `fail()` logic.

## Verification

Simulation with 10 normal jobs + 2 error jobs across 5 concurrent workers:
- Before: Done=10, Failed=0, Stuck=2 — every job processed by all 5 workers
- After: Done=10, Failed=2, Stuck=0 — each job processed once, errors retried then properly failed
