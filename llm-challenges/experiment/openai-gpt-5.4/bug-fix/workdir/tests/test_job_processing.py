import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_queue import JobQueue
from worker import process_job


async def _run_workers(queue: JobQueue, worker_count: int = 5) -> None:
    workers = [process_job(queue, i) for i in range(worker_count)]
    await asyncio.gather(*workers)


def test_should_process_each_job_once_and_mark_exhausted_failures() -> None:
    queue = JobQueue(max_retries=2)

    for i in range(10):
        queue.enqueue({"name": f"task_{i}", "raise_error": False})
    failing_job_ids = [
        queue.enqueue({"name": "bad_task_1", "raise_error": True}),
        queue.enqueue({"name": "bad_task_2", "raise_error": True}),
    ]

    asyncio.run(_run_workers(queue))

    jobs = queue.all_jobs
    done = [job for job in jobs.values() if job["status"] == "done"]
    failed = [job for job in jobs.values() if job["status"] == "failed"]
    processing = [job for job in jobs.values() if job["status"] == "processing"]

    assert len(done) == 10
    assert len(failed) == 2
    assert not processing

    for job in done:
        assert str(job["result"]).startswith("processed by worker ")

    for job_id in failing_job_ids:
        job = jobs[job_id]
        assert job["status"] == "failed"
        assert job["retries"] == 2
        assert job["result"] == f"processing error for job {job_id}"
