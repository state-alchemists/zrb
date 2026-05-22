"""Stress test to reproduce production bugs."""
import asyncio
from job_queue import JobQueue
from worker import process_job


async def main() -> None:
    print("=== Test 1: Basic simulation (already passes) ===")
    queue = JobQueue(max_retries=2)
    for i in range(10):
        queue.enqueue({"name": f"task_{i}", "raise_error": False})
    queue.enqueue({"name": "bad_task_1", "raise_error": True})
    queue.enqueue({"name": "bad_task_2", "raise_error": True})
    workers = [process_job(queue, i) for i in range(5)]
    await asyncio.gather(*workers)
    jobs = queue.all_jobs
    done = [j for j in jobs.values() if j["status"] == "done"]
    failed = [j for j in jobs.values() if j["status"] == "failed"]
    stuck = [j for j in jobs.values() if j["status"] == "processing"]
    pending = [j for j in jobs.values() if j["status"] == "pending"]
    print(f"Done: {len(done)}, Failed: {len(failed)}, Stuck: {len(stuck)}, Pending: {len(pending)}")

    print("\n=== Test 2: More workers than jobs (trigger vanishing failures) ===")
    queue2 = JobQueue(max_retries=3)
    for i in range(3):
        queue2.enqueue({"name": f"good_{i}", "raise_error": False})
    queue2.enqueue({"name": "bad", "raise_error": True})
    workers = [process_job(queue2, i) for i in range(10)]
    await asyncio.gather(*workers)
    jobs = queue2.all_jobs
    done = [j for j in jobs.values() if j["status"] == "done"]
    failed = [j for j in jobs.values() if j["status"] == "failed"]
    stuck = [j for j in jobs.values() if j["status"] == "processing"]
    pending = [j for j in jobs.values() if j["status"] == "pending"]
    print(f"Done: {len(done)}, Failed: {len(failed)}, Stuck: {len(stuck)}, Pending: {len(pending)}")
    print(f"Expected: 3 done, 1 failed, 0 stuck, 0 pending")

    print("\n=== Test 3: All jobs fail (trigger duplicate processing) ===")
    queue3 = JobQueue(max_retries=2)
    for i in range(5):
        queue3.enqueue({"name": f"fail_{i}", "raise_error": True})
    workers = [process_job(queue3, i) for i in range(3)]
    await asyncio.gather(*workers)
    jobs = queue3.all_jobs
    done = [j for j in jobs.values() if j["status"] == "done"]
    failed = [j for j in jobs.values() if j["status"] == "failed"]
    stuck = [j for j in jobs.values() if j["status"] == "processing"]
    pending = [j for j in jobs.values() if j["status"] == "pending"]
    print(f"Done: {len(done)}, Failed: {len(failed)}, Stuck: {len(stuck)}, Pending: {len(pending)}")
    print(f"Expected: 0 done, 5 failed, 0 stuck, 0 pending")

    print("\n=== Test 4: max_retries=0 (fail immediately) ===")
    queue4 = JobQueue(max_retries=0)
    queue4.enqueue({"name": "bad", "raise_error": True})
    workers = [process_job(queue4, i) for i in range(3)]
    await asyncio.gather(*workers)
    jobs = queue4.all_jobs
    done = [j for j in jobs.values() if j["status"] == "done"]
    failed = [j for j in jobs.values() if j["status"] == "failed"]
    stuck = [j for j in jobs.values() if j["status"] == "processing"]
    pending = [j for j in jobs.values() if j["status"] == "pending"]
    print(f"Done: {len(done)}, Failed: {len(failed)}, Stuck: {len(stuck)}, Pending: {len(pending)}")
    print(f"Expected: 0 done, 1 failed, 0 stuck, 0 pending")

    print("\n=== Test 5: Single worker, queue of bad jobs ===")
    queue5 = JobQueue(max_retries=1)
    for i in range(3):
        queue5.enqueue({"name": f"bad_{i}", "raise_error": True})
    workers = [process_job(queue5, i) for i in range(1)]
    await asyncio.gather(*workers)
    jobs = queue5.all_jobs
    done = [j for j in jobs.values() if j["status"] == "done"]
    failed = [j for j in jobs.values() if j["status"] == "failed"]
    stuck = [j for j in jobs.values() if j["status"] == "processing"]
    pending = [j for j in jobs.values() if j["status"] == "pending"]
    print(f"Done: {len(done)}, Failed: {len(failed)}, Stuck: {len(stuck)}, Pending: {len(pending)}")
    print(f"Expected: 0 done, 3 failed, 0 stuck, 0 pending")


if __name__ == "__main__":
    asyncio.run(main())
