"""Test that reproduces the two reported bugs by stressing concurrent access."""
import asyncio
from job_queue import JobQueue
from worker import process_job


async def test_duplicate_processing():
    """Bug 1: With many workers racing on dequeue, the same job can be 
    dequeued by two workers."""
    for trial in range(50):
        q = JobQueue(max_retries=0)
        q.enqueue({"name": "only_job", "raise_error": False})
        # 3 workers racing for 1 job — only 1 should process it
        workers = [process_job(q, i) for i in range(3)]
        await asyncio.gather(*workers)
        jobs = q.all_jobs
        done = [j for j in jobs.values() if j["status"] == "done"]
        stuck = [j for j in jobs.values() if j["status"] == "processing"]
        pending = [j for j in jobs.values() if j["status"] == "pending"]
        if len(done) != 1 or len(stuck) != 0 or len(pending) != 0:
            print(f"  Trial {trial}: DUPLICATE! done={len(done)}, stuck={len(stuck)}, pending={len(pending)}")
            return False
    print("  No duplicate processing detected (50 trials)")
    return True


async def test_vanishing_failures():
    """Bug 2: Failed jobs disappear instead of being marked as failed."""
    for trial in range(50):
        q = JobQueue(max_retries=2)
        # All bad jobs
        for i in range(3):
            q.enqueue({"name": f"bad_{i}", "raise_error": True})
        workers = [process_job(q, i) for i in range(5)]
        await asyncio.gather(*workers)
        jobs = q.all_jobs
        failed = [j for j in jobs.values() if j["status"] == "failed"]
        stuck = [j for j in jobs.values() if j["status"] == "processing"]
        pending = [j for j in jobs.values() if j["status"] == "pending"]
        if len(failed) != 3 or len(stuck) != 0 or len(pending) != 0:
            print(f"  Trial {trial}: VANISHED! failed={len(failed)}, stuck={len(stuck)}, pending={len(pending)}")
            return False
    print("  No vanishing failures detected (50 trials)")
    return True


async def test_concurrent_enqueue_dequeue():
    """Stress test: concurrent enqueue and dequeue operations."""
    for trial in range(30):
        q = JobQueue(max_retries=2)
        # Add some initial jobs
        for i in range(5):
            q.enqueue({"name": f"initial_{i}", "raise_error": False})

        async def late_enqueue():
            await asyncio.sleep(0.02)
            q.enqueue({"name": "late_bad", "raise_error": True})

        # Start workers and late enqueue
        workers = [process_job(q, i) for i in range(3)]
        workers.append(late_enqueue())
        await asyncio.gather(*workers)
        
        jobs = q.all_jobs
        done = [j for j in jobs.values() if j["status"] == "done"]
        failed = [j for j in jobs.values() if j["status"] == "failed"]
        stuck = [j for j in jobs.values() if j["status"] == "processing"]
        pending = [j for j in jobs.values() if j["status"] == "pending"]
        if stuck or pending:
            print(f"  Trial {trial}: STUCK! done={len(done)}, failed={len(failed)}, stuck={len(stuck)}, pending={len(pending)}")
            return False
    print("  No concurrent enqueue/dequeue issues (30 trials)")
    return True


async def main():
    print("=== Bug 1: Duplicate Processing ===")
    await test_duplicate_processing()
    
    print("\n=== Bug 2: Vanishing Failures ===")
    await test_vanishing_failures()
    
    print("\n=== Bonus: Concurrent Enqueue ===")
    await test_concurrent_enqueue_dequeue()


if __name__ == "__main__":
    asyncio.run(main())
