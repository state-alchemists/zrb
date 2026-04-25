#!/usr/bin/env python3
import asyncio
import os
import sys


def verify():
    print("Verifying Job Queue Fix...")

    for fname in ["job_queue.py", "worker.py"]:
        if not os.path.exists(fname):
            print(f"FAIL: {fname} not found")
            print("VERIFICATION_RESULT: FAIL")
            return False

    sys.path.insert(0, os.getcwd())

    try:
        from job_queue import JobQueue
        from worker import process_job
    except ImportError as e:
        print(f"FAIL: Import error: {e}")
        print("VERIFICATION_RESULT: FAIL")
        return False

    with open("job_queue.py") as f:
        queue_src = f.read()
    with open("worker.py") as f:
        worker_src = f.read()
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

    passes = 0
    runs = 5
    for run in range(runs):
        done, failed, stuck = asyncio.run(run_simulation())
        ok = done == 10 and failed == 2 and stuck == 0
        status = "PASS" if ok else f"FAIL (done={done}, failed={failed}, stuck={stuck})"
        print(f"  Run {run + 1}: {status}")
        if ok:
            passes += 1

    if passes < runs:
        print(f"FAIL: Only {passes}/{runs} simulation runs passed")
        print("VERIFICATION_RESULT: FAIL")
        return False

    if has_lock:
        print("PASS: Concurrency control (Lock) detected")
        print("VERIFICATION_RESULT: EXCELLENT")
    else:
        print("PASS: All simulation runs passed")
        print("VERIFICATION_RESULT: PASS")
    return True


if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)
