import asyncio

from job_queue import JobQueue
from worker import process_job


async def _dequeue_once(queue: JobQueue):
    job = await queue.dequeue()
    return None if job is None else job["id"]


async def _dequeue_many(queue: JobQueue, count: int):
    return await asyncio.gather(*[_dequeue_once(queue) for _ in range(count)])


def test_should_dequeue_each_pending_job_only_once_under_concurrency():
    queue = JobQueue()
    for index in range(5):
        queue.enqueue({"name": f"task_{index}", "raise_error": False})

    job_ids = asyncio.run(_dequeue_many(queue, 5))

    assert sorted(job_ids) == [1, 2, 3, 4, 5]
    assert all(job["status"] == "processing" for job in queue.all_jobs.values())


def test_should_mark_job_failed_after_max_retries_when_worker_raises():
    queue = JobQueue(max_retries=2)
    job_id = queue.enqueue({"name": "bad_task", "raise_error": True})

    asyncio.run(process_job(queue, worker_id=1))

    job = queue.all_jobs[job_id]
    assert job["status"] == "failed"
    assert job["retries"] == 2
    assert job["result"] == f"processing error for job {job_id}"
