import asyncio
from typing import Any, Dict, List, Optional


class JobQueue:
    def __init__(self, max_retries: int = 3):
        self._jobs: Dict[int, Dict[str, Any]] = {}
        self._pending_order: List[int] = []  # Maintain insertion order
        self._next_id = 1
        self.max_retries = max_retries
        self._lock = asyncio.Lock()

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
        self._pending_order.append(job_id)
        return job_id

    async def dequeue(self) -> Optional[Dict]:
        async with self._lock:
            while self._pending_order:
                job_id = self._pending_order.pop(0)
                job = self._jobs[job_id]
                if job["status"] == "pending":
                    job["status"] = "processing"
                    return job
        return None

    async def fail(self, job_id: int, error: str) -> Optional[Dict]:
        async with self._lock:
            job = self._jobs[job_id]
            job["retries"] += 1
            if job["retries"] > self.max_retries:
                job["status"] = "failed"
                job["result"] = error
                return None
            # Put at end of queue for retry after other pending jobs
            job["status"] = "pending"
            self._pending_order.append(job_id)
        return job

    def complete(self, job_id: int, result: Any) -> None:
        self._jobs[job_id]["status"] = "done"
        self._jobs[job_id]["result"] = result

    @property
    def all_jobs(self) -> Dict[int, Dict]:
        return self._jobs
