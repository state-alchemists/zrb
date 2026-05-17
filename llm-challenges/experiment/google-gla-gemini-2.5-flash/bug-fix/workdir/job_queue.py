import asyncio
from typing import Any, Dict, Optional


class JobQueue:
    def __init__(self, max_retries: int = 3, processing_timeout: int = 60):
        self._jobs: Dict[int, Dict[str, Any]] = {}
        self._pending_queue = asyncio.Queue()  # Use asyncio.Queue for pending jobs
        self._processing_jobs: Dict[int, Dict[str, Any]] = {}
        self._next_id = 1
        self.max_retries = max_retries
        self.processing_timeout = processing_timeout

    def enqueue(self, payload: dict) -> int:
        job_id = self._next_id
        self._next_id += 1
        job = {
            "id": job_id,
            "payload": payload,
            "status": "pending",
            "retries": 0,
            "result": None,
            "last_processed_time": None,  # Add last_processed_time
        }
        self._jobs[job_id] = job
        self._pending_queue.put_nowait(job_id)  # Add job ID to the queue
        return job_id

    async def dequeue(self) -> Optional[Dict]:
        try:
            job_id = await self._pending_queue.get()  # Get job ID from the queue
            job = self._jobs[job_id]
            job["status"] = "processing"
            job["last_processed_time"] = asyncio.get_event_loop().time()  # Record time
            self._processing_jobs[job_id] = job
            return job
        except asyncio.QueueEmpty:
            return None
        return None

    def complete(self, job_id: int, result: Any) -> None:
        job = self._jobs[job_id]
        job["status"] = "done"
        job["result"] = result
        if job_id in self._processing_jobs:
            del self._processing_jobs[job_id]

    def fail(self, job_id: int, error: str) -> None:
        job = self._jobs[job_id]
        if job_id in self._processing_jobs:
            del self._processing_jobs[job_id]

        if job["retries"] < self.max_retries:
            job["retries"] += 1
            job["status"] = "pending"
            self._pending_queue.put_nowait(job_id)  # Re-enqueue for retry
        else:
            job["status"] = "failed"
            job["result"] = error

    async def reclaim_stalled_jobs(self) -> None:
        current_time = asyncio.get_event_loop().time()
        stalled_job_ids = []
        for job_id, job in self._processing_jobs.items():
            if (current_time - job["last_processed_time"]) > self.processing_timeout:
                stalled_job_ids.append(job_id)

        for job_id in stalled_job_ids:
            print(f"[Queue] Reclaiming stalled job {job_id}")
            self.fail(job_id, "Job stalled during processing")

    @property
    def all_jobs(self) -> Dict[int, Dict]:
        return self._jobs
