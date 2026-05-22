"""
Aggressive reproduction test for bugs:
1. Duplicate processing - jobs processed more than once
2. Vanishing failures - jobs never reach "failed"

Tests with dynamic enqueue + many workers + concurrent operations.
"""
import asyncio
from job_queue import JobQueue
from worker import process_job
from collections import Counter


async def run_trial(workers_count: int = 10, delay: float = 0.0) -> dict:
    queue = JobQueue(max_retries=2)

    # Enqueue good jobs upfront
    for i in range(5):
        queue.enqueue({"name": f"good_{i}", "raise_error": False})

    # Start workers
    workers = [asyncio.create_task(process_job(queue, i)) for i in range(workers_count)]

    # Dynamically enqueue more jobs while workers are running
    await asyncio.sleep(delay)
    for i in range(5, 10):
        queue.enqueue({"name": f"good_{i}", "raise_error": False})
    await asyncio.sleep(delay)

    # Enqueue bad jobs dynamically too
    queue.enqueue({"name": "bad_1", "raise_error": True})
    queue.enqueue({"name": "bad_2", "raise_error": True})
    await asyncio.sleep(delay)

    # Give workers time to process
    await asyncio.sleep(0.5)

    # Cancel any stuck workers
    for w in workers:
        if not w.done():
            w.cancel()

    # Wait for all to finish (or be cancelled)
    await asyncio.gather(*workers, return_exceptions=True)

    jobs = queue.all_jobs
    done = [j for j in jobs.values() if j["status"] == "done"]
    failed = [j for j in jobs.values() if j["status"] == "failed"]
    stuck = [j for j in jobs.values() if j["status"] == "processing"]
    pending = [j for j in jobs.values() if j["status"] == "pending"]

    issues = []
    if len(done) != 10:
        issues.append(f"done={len(done)} expected=10")
    if len(failed) != 2:
        issues.append(f"failed={len(failed)} expected=2")
    if stuck:
        issues.append(f"stuck={len(stuck)} ids={[j['id'] for j in stuck]}")
    if pending:
        issues.append(f"pending={len(pending)} ids={[j['id'] for j in pending]}")

    # Verify retry counts
    for jid, job in jobs.items():
        if job["payload"].get("raise_error"):
            if job["status"] != "failed":
                issues.append(f"bad job {jid} status={job['status']} (should be 'failed')")
            elif job["retries"] != 2:
                issues.append(f"bad job {jid} retries={job['retries']} expected=2")
        elif job["status"] == "done" and job["retries"] != 0:
            issues.append(f"good job {jid} has retries={job['retries']} (should be 0)")

    return {"ok": not issues, "issues": issues, "done": len(done), "failed": len(failed),
            "stuck": len(stuck), "pending": len(pending)}


async def main():
    configs = [
        (5, 0.0),
        (10, 0.0),
        (20, 0.01),
        (50, 0.0),
    ]

    for workers, delay in configs:
        print(f"\n=== {workers} workers, delay={delay} ===")
        n_trials = 100
        results = []
        for t in range(n_trials):
            r = await run_trial(workers, delay)
            results.append(r)

        ok_count = sum(1 for r in results if r["ok"])
        fail_count = n_trials - ok_count
        print(f"Passed: {ok_count}/{n_trials}, Failed: {fail_count}/{n_trials}")

        all_issues = Counter()
        for r in results:
            for issue in r["issues"]:
                all_issues[issue] += 1
        if all_issues:
            print("Issues breakdown:")
            for issue, count in all_issues.most_common():
                print(f"  {issue}: {count}x")


if __name__ == "__main__":
    asyncio.run(main())
