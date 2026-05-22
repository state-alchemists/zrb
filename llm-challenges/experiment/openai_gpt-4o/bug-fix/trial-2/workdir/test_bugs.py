"""Diagnose bugs in the job queue system."""
import asyncio
from job_queue import JobQueue
from worker import process_job


async def test_single_worker():
    """See what happens with a single worker processing a failing job."""
    queue = JobQueue(max_retries=2)
    for i in range(3):
        queue.enqueue({"name": f"ok_{i}", "raise_error": False})
    queue.enqueue({"name": "bad", "raise_error": True})

    await process_job(queue, 0)

    print("=== Single worker done ===")
    for jid, j in sorted(queue.all_jobs.items()):
        print(f"  Job {jid}: status={j['status']}, retries={j['retries']}")


async def test_concurrent_fail():
    """Stress test: many failing jobs with many workers."""
    queue = JobQueue(max_retries=1)
    for i in range(20):
        queue.enqueue({"name": f"task_{i}", "raise_error": i % 3 == 0})

    workers = [process_job(queue, i) for i in range(5)]
    await asyncio.gather(*workers)

    jobs = queue.all_jobs
    done = [j for j in jobs.values() if j["status"] == "done"]
    failed = [j for j in jobs.values() if j["status"] == "failed"]
    processing = [j for j in jobs.values() if j["status"] == "processing"]
    pending = [j for j in jobs.values() if j["status"] == "pending"]

    print(f"\n=== Concurrent test ===")
    print(f"Total: {len(jobs)}")
    print(f"Done: {len(done)}")
    print(f"Failed: {len(failed)}")
    print(f"Processing (stuck): {len(processing)}")
    print(f"Pending (stuck): {len(pending)}")
    if processing or pending:
        print("  STUCK JOBS DETECTED!")
        for j in processing:
            print(f"    Job {j['id']}: processing")
        for j in pending:
            print(f"    Job {j['id']}: pending")
    # Check for duplicate processing by looking at retries on done jobs
    for j in jobs.values():
        if j["status"] == "done" and j["retries"] > 0:
            print(f"  WARNING: Job {j['id']} done but retried {j['retries']} times!")


async def test_vanishing_failure():
    """Check if exceptions in process_job cause jobs to vanish."""
    queue = JobQueue(max_retries=2)
    queue.enqueue({"name": "bad", "raise_error": True})
    queue.enqueue({"name": "ok", "raise_error": False})

    await process_job(queue, 0)

    jobs = queue.all_jobs
    print(f"\n=== Vanishing failure test ===")
    for jid, j in sorted(jobs.items()):
        print(f"  Job {jid}: name={j['payload']['name']}, status={j['status']}, retries={j['retries']}")


if __name__ == "__main__":
    asyncio.run(test_single_worker())
    asyncio.run(test_concurrent_fail())
    asyncio.run(test_vanishing_failure())
