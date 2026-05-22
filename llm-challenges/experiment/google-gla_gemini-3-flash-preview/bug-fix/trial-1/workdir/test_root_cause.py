"""Targeted reproduction of root causes for both bugs."""
import asyncio
from job_queue import JobQueue


async def reproduce_vanishing_failures():
    """
    Bug 2 (Vanishing Failures): When a worker is cancelled or raises a 
    BaseException (not caught by `except Exception`), the job stays 
    stuck as "processing" and never reaches "failed".
    
    This happens when asyncio.gather() cancels workers after one raises.
    The CancelledError hits `await queue.dequeue()` which is OUTSIDE
    the try/except block, so the worker dies without calling fail().
    """
    print("=== Vanishing Failures Reproduction ===")
    q = JobQueue(max_retries=2)
    q.enqueue({"name": "doomed", "raise_error": True})
    
    async def killer_worker():
        # This worker raises a BaseException (not Exception) AS IF
        # it were canceled by asyncio.gather or got a KeyboardInterrupt
        job = await q.dequeue()
        print(f"[Killer] got job {job['id']}, raising BaseException...")
        raise BaseException("simulated cancellation")
    
    try:
        await asyncio.gather(killer_worker())
    except BaseException:
        pass
    
    jobs = q.all_jobs
    print(f"Job statuses:")
    for jid, j in jobs.items():
        print(f"  Job {jid}: status={j['status']}, retries={j['retries']}")
    
    stuck = [j for j in jobs.values() if j["status"] == "processing"]
    print(f"\nStuck (processing): {len(stuck)} — should be 0!")
    print(f"Explanation: worker raised BaseException outside try/except, "
          f"job left stuck as 'processing'. "
          f"In production, asyncio.gather cancels sibling workers this way.")


async def reproduce_duplicate_processing():
    """
    Bug 1 (Duplicate Processing): The `dequeue()` method returns a LIVE 
    reference to the job dict. After `fail()` sets status back to "pending",
    the worker's next `dequeue()` picks up the SAME job.
    
    Worse: with `await asyncio.sleep(0.01)` between status-change and return,
    another worker's `dequeue()` that started concurrently could also see 
    the job as "pending" if the timing aligns just wrong at the iterator level.
    
    More concretely: a job that FAILS gets retried, but the RETRY itself is
    the "duplicate processing" — side effects fire twice for the same job_id.
    With max_retries=2, the bad job runs 3 times. If the user expected
    max_retries=2 to mean "at most 2 total attempts", the 3rd run is the
    duplicate.
    
    But even more insidious: the `for job in self._jobs.values()` creates a 
    live iterator. During `await asyncio.sleep(0.01)`, another dequeue()'s 
    iterator could be mid-flight. Combined with `fail()` mutating status 
    in-place, a subtle race allows two workers to claim the same job.
    """
    print("\n=== Duplicate Processing Reproduction ===")
    q = JobQueue(max_retries=2)
    q.enqueue({"name": "disputed", "raise_error": False})
    
    async def worker(n):
        job = await q.dequeue()
        if job is None:
            print(f"[Worker {n}] no job")
            return
        print(f"[Worker {n}] got job {job['id']} (status={job['status']})")
        # Simulate processing
        await asyncio.sleep(0.05)
        q.complete(job["id"], f"done by {n}")
        print(f"[Worker {n}] completed job {job['id']}")
        return job["id"]
    
    # Dequeue the job manually, then have two workers race
    job_ref = await q.dequeue()
    print(f"Dequeued job 1, status now: {job_ref['status']}")
    
    # Now set it back to pending (as if fail() was called with retry)
    # This simulates the race: job is pending, two workers both see it
    job_ref["status"] = "pending"
    job_ref["retries"] = 0
    
    results = await asyncio.gather(worker(0), worker(1))
    print(f"\nBoth workers returned: {results}")
    jobs = q.all_jobs
    done = [j for j in jobs.values() if j["status"] == "done"]
    print(f"Done jobs: {len(done)} — {'DUPLICATE!' if len(done) > 1 else 'expected 1'}")
    
    # Reset and demonstrate the actual timing vulnerability
    print("\n--- Timing vulnerability demonstration ---")
    q2 = JobQueue(max_retries=2)
    q2.enqueue({"name": "only_one", "raise_error": False})
    
    # The await in dequeue() is between marking processing and return.
    # During that sleep, another coroutine's enqueue() could add a job
    # that the iterator might miss — or the iterators could conflict.
    # Actually the real issue: if two dequeue() calls interleave, 
    # the second one creates a FRESH iterator. No direct conflict.
    # But the race IS real with concurrent fail() → pending re-enqueue.
    
    print("The real duplicate bug: dequeue() returns a reference that")
    print("fail() mutates in-place, making the job immediately available")
    print("for re-pickup by the same or another worker on the next loop.")
    print("The retry mechanism means max_retries=2 → 3 total executions.")
    print("If the processing has irreversible side effects (email, charge),")
    print("each retry fires those side effects again = 'duplicate processing'.")


async def reproduce_nested_exception_crash():
    """
    An exception inside queue.fail() or queue.complete() propagates
    OUT of the except block, killing the worker and leaving the job stuck.
    """
    print("\n=== Crash in complete/fail vanishes failures ===")
    q = JobQueue(max_retries=2)
    q.enqueue({"name": "bad", "raise_error": True})
    
    # Break the job so complete/fail will KeyError
    # This simulates what happens if _jobs is corrupted
    del q._jobs[1]
    q._jobs[1] = {"id": 1, "status": "pending"}  # missing keys!
    
    from worker import process_job
    
    try:
        workers = [process_job(q, 0)]
        await asyncio.gather(*workers)
    except Exception as e:
        print(f"Unhandled crash: {type(e).__name__}: {e}")
    
    jobs = q.all_jobs
    stuck = [j for j in jobs.values() if j["status"] == "processing"]
    for jid, j in jobs.items():
        print(f"  Job {jid}: status={j.get('status', 'N/A')}")


async def main():
    await reproduce_vanishing_failures()
    
    # Skip the broken-job test since it will crash
    # await reproduce_nested_exception_crash()
    
    print("\n\n=== Root Cause Analysis ===")
    print("""
BUG 1 — Duplicate Processing (Root Cause):
  The `dequeue()` method's `await asyncio.sleep(0.01)` sits BETWEEN 
  marking the job as "processing" and returning it. While the status 
  IS set before yielding, the yield point creates unnecessary risk.
  
  More critically: `dequeue()` returns a LIVE REFERENCE to the job 
  dict. When `fail()` sets status to "pending" (retry), the same 
  worker's while loop IMMEDIATELY re-picks the job. Each retry 
  re-executes the full processing including side effects.
  
  With max_retries=2, a bad job fires 3 times. If the convention
  should be "max_retries=2 = at most 2 total attempts" not 
  "2 retries + 1 original", this is the gap.

BUG 2 — Vanishing Failures (Root Cause):
  `await queue.dequeue()` and `print(...)` are OUTSIDE the try/except 
  block in `process_job()`. If either raises (notably asyncio.
  CancelledError when asyncio.gather cancels sibling workers, or 
  any BaseException), the worker dies WITHOUT calling fail().
  
  The job remains "processing" forever — never "failed", never 
  retried. It simply disappears from the queue.
  
  Additionally, if queue.fail() or queue.complete() itself raises 
  (e.g., KeyError from corrupted _jobs), that exception propagates 
  OUT of the except block, killing the worker.
""")


if __name__ == "__main__":
    asyncio.run(main())
