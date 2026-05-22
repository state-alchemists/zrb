import asyncio


async def process_job(queue, worker_id: int) -> None:
    while True:
        job = None
        try:
            job = await queue.dequeue()
            if job is None:
                return

            print(f"[Worker {worker_id}] picked up job {job['id']}")
            await asyncio.sleep(0.05)

            if job["payload"].get("raise_error"):
                raise RuntimeError(f"processing error for job {job['id']}")

            queue.complete(job["id"], f"processed by worker {worker_id}")
            print(f"[Worker {worker_id}] finished job {job['id']}")
        except GeneratorExit:
            raise
        except BaseException as e:
            if job is not None:
                print(f"[Worker {worker_id}] job {job['id']} failed: {e}")
                queue.fail(job["id"], str(e))
            if not isinstance(e, Exception):
                raise
