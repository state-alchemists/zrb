import asyncio
from job_queue import JobQueue
from worker import process_job
from asyncio import QueueEmpty # Correct import

async def periodic_reclaimer(queue: JobQueue, interval: float = 1) -> None:
    try:
        while True:
            await queue.reclaim_stalled_jobs()
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        print("[Reclaimer] Shutting down")

async def main() -> None:
    queue = JobQueue(max_retries=2, processing_timeout=1)  # Shorter timeout for simulation

    for i in range(10):
        queue.enqueue({"name": f"task_{i}", "raise_error": False})
    queue.enqueue({"name": "bad_task_1", "raise_error": True})
    queue.enqueue({"name": "bad_task_2", "raise_error": True})

    async def shutdown_workers(workers, timeout=0.5):
        for worker_task in workers:
            worker_task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        await asyncio.sleep(timeout)

    workers = [asyncio.create_task(process_job(queue, i)) for i in range(5)]
    reclaimer_task = asyncio.create_task(periodic_reclaimer(queue, interval=0.5))

    # Wait for all jobs to be processed or failed. This is a heuristic for the simulation.
    # In a real system, you'd have a more robust way to know when to stop.
    await asyncio.sleep(5)  # Give time for initial processing and reclaims

    print("\n=== Initiating shutdown ===")
    reclaimer_task.cancel()
    await shutdown_workers(workers)
    await reclaimer_task

    # Give some time for reclaimed jobs to be processed or marked as failed
    await asyncio.sleep(0.5)

    jobs = queue.all_jobs
    done = [j for j in jobs.values() if j["status"] == "done"]
    failed = [j for j in jobs.values() if j["status"] == "failed"]
    stuck = [j for j in jobs.values() if j["status"] == "processing"]

    print(f"\n=== Results ===")
    print(f"Done:   {len(done)} (expected 10)")
    print(f"Failed: {len(failed)} (expected 2)")
    print(f"Stuck:  {len(stuck)} (expected 0)")


if __name__ == "__main__":
    asyncio.run(main())
