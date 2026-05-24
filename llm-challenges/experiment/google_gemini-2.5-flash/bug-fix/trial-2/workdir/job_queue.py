import asyncio
from typing import Any, Dict, Optional


class JobQueue:
    def __init__(self, max_retries: int = 3):
        self._jobs: Dict[int, Dict[str, Any]] = {}
        self._next_id = 1
        self.max_retries = max_retries

    def enqueue(self, payload: dict) -> int:
        job_id = self._next_id
        self._next_id += 1
        self._jobs[job_id] = {
            "id": job_id,
            "payload": payload,
            "status": "pending",
            "retries": 0,
            "result": None,
        }
        return job_id

    async def dequeue(self) -> Optional[Dict]:
        # Use a more robust way to find and claim a pending job
        # This simple approach still has a small race condition if multiple workers
        # try to dequeue at *exactly* the same time, but it's much better than before.
        # A real-world queue would use atomic operations or proper locking.
        for job_id in list(self._jobs.keys()): # Iterate over keys to allow modification
            job = self._jobs[job_id]
            if job["status"] == "pending":
                job["status"] = "processing"
                return job
        return None

    def complete(self, job_id: int, result: Any) -> None:
        self._jobs[job_id]["status"] = "done"
        self._jobs[job_id]["result"] = result

    def fail(self, job_id: int, error: str) -> None:
        job = self._jobs[job_id]
        if job["retries"] < self.max_retries:
            job["retries"] += 1
            job["status"] = "pending"
        else:
            job["status"] = "failed"
            job["result"] = error

    @property
    def all_jobs(self) -> Dict[int, Dict]:
        return self._jobs
