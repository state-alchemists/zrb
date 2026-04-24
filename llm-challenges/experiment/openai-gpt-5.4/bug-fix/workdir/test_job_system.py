import asyncio

from job_queue import JobQueue
from worker import process_job


async def _run_workers(queue: JobQueue, count: int = 5) -> None:
    await asyncio.gather(*(process_job(queue, worker_id) for worker_id in range(count)))


def test_should_process_each_job_once_when_multiple_workers_compete() -> None:
    queue = JobQueue()
    for i in range(4):
        queue.enqueue({"name": f"task_{i}", "raise_error": False})

    asyncio.run(_run_workers(queue, count=5))

    jobs = queue.all_jobs
    assert all(job["status"] == "done" for job in jobs.values())
    assert {job["result"] for job in jobs.values()} == {
        "processed by worker 0",
        "processed by worker 1",
        "processed by worker 2",
        "processed by worker 3",
    }


def test_should_mark_job_failed_after_retries_are_exhausted() -> None:
    queue = JobQueue(max_retries=2)
    queue.enqueue({"name": "bad_task", "raise_error": True})

    asyncio.run(_run_workers(queue, count=1))

    job = queue.all_jobs[1]
    assert job["status"] == "failed"
    assert job["retries"] == 2
    assert job["result"] == "processing error for job 1"
