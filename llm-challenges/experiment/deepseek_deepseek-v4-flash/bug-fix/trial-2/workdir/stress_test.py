import asyncio
from job_queue import JobQueue
from worker import process_job
from collections import Counter


async def run_trial(trial_id: int) -> dict:
    queue = JobQueue(max_retries=2)

    # Enqueue 10 good jobs + 2 bad jobs
    for i in range(10):
        queue.enqueue({"name": f"task_{i}", "raise_error": False})
    queue.enqueue({"name": "bad_task_1", "raise_error": True})
    queue.enqueue({"name": "bad_task_2", "raise_error": True})

    # Use many workers for more contention
    workers = [process_job(queue, i) for i in range(20)]
    await asyncio.gather(*workers)

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
        issues.append(f"stuck={len(stuck)} job_ids={[j['id'] for j in stuck]}")
    if pending:
        issues.append(f"pending={len(pending)} job_ids={[j['id'] for j in pending]}")

    # Check retry counts
    for jid, job in jobs.items():
        if job["status"] == "failed" and job["retries"] != 2:
            issues.append(f"job {jid} failed with retries={job['retries']} expected=2")
        if job["status"] == "done" and job["retries"] != 0:
            issues.append(f"job {jid} done with retries={job['retries']} expected=0")
        # For bad jobs, they should have been processed exactly 3 times (initial + 2 retries)
        if job["payload"].get("raise_error"):
            # Count total retries = number of times fail() was called
            pass

    return {"trial": trial_id, "ok": not issues, "issues": issues, "done": len(done), "failed": len(failed), "stuck": len(stuck), "pending": len(pending)}


async def main():
    n_trials = 50
    results = []
    for t in range(n_trials):
        r = await run_trial(t)
        results.append(r)
        status = "OK" if r["ok"] else "FAIL"
        if not r["ok"]:
            print(f"Trial {t}: {status} - {'; '.join(r['issues'])}")

    ok_count = sum(1 for r in results if r["ok"])
    fail_count = n_trials - ok_count
    print(f"\n=== Summary ===\nPassed: {ok_count}/{n_trials}\nFailed: {fail_count}/{n_trials}")

    # Collect all issues
    all_issues = Counter()
    for r in results:
        for issue in r["issues"]:
            all_issues[issue] += 1
    if all_issues:
        print("\nIssues breakdown:")
        for issue, count in all_issues.most_common():
            print(f"  {issue}: {count}x")


if __name__ == "__main__":
    asyncio.run(main())
