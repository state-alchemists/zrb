import asyncio, sys
sys.path.insert(0, '.')
from job_queue import JobQueue
from worker import process_job

async def run_simulation():
    q = JobQueue(max_retries=2)
    for i in range(10):
        q.enqueue({'name': f'task_{i}', 'raise_error': False})
    q.enqueue({'name': 'bad_1', 'raise_error': True})
    q.enqueue({'name': 'bad_2', 'raise_error': True})
    workers = [process_job(q, i) for i in range(5)]
    await asyncio.gather(*workers)
    jobs = q.all_jobs
    done = sum(1 for j in jobs.values() if j['status'] == 'done')
    failed = sum(1 for j in jobs.values() if j['status'] == 'failed')
    processing = sum(1 for j in jobs.values() if j['status'] == 'processing')
    pending = sum(1 for j in jobs.values() if j['status'] == 'pending')
    return done, failed, processing, pending

anomalies = 0
for i in range(200):
    done, failed, processing, pending = asyncio.run(run_simulation())
    if done != 10 or failed != 2 or processing != 0 or pending != 0:
        anomalies += 1
        print(f'ANOMALY run {i}: done={done} failed={failed} processing={processing} pending={pending}')

if anomalies:
    print(f'\n{anomalies} anomalies found in 200 runs')
else:
    print(f'All 200 runs passed (done=10, failed=2, stuck=0)')
