import asyncio

from job_queue import JobQueue
from worker import process_job


async def _run_workers(queue: JobQueue, worker_count: int) -> None:
    await asyncio.gather(*(process_job(queue, worker_id) for worker_id in range(worker_count)))


def test_should_process_each_job_once_when_multiple_workers_compete() -> None:
    queue = JobQueue()
    job_id = queue.enqueue({"name": "task", "raise_error": False})

    asyncio.run(_run_workers(queue, worker_count=5))

    jobs = queue.all_jobs
    assert len(jobs) == 1

    job = jobs[job_id]
    assert job["status"] == "done"
    assert job["result"].startswith("processed by worker ")
    assert job["retries"] == 0


def test_should_mark_job_failed_after_retries_when_worker_raises() -> None:
    queue = JobQueue(max_retries=2)
    job_id = queue.enqueue({"name": "bad_task", "raise_error": True})

    asyncio.run(_run_workers(queue, worker_count=1))

    job = queue.all_jobs[job_id]
    assert job["status"] == "failed"
    assert job["retries"] == 2
    assert job["result"] == f"processing error for job {job_id}"
