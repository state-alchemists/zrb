Our background job processor has been acting up in production. Two separate issues have been reported:

1. **Duplicate processing**: Some jobs appear to be executed more than once. We've seen side effects (emails, charges) triggered twice for a single job ID.
2. **Vanishing failures**: Jobs that crash with an exception never show up as "failed". They seem to just disappear from the queue, making retries impossible.

The system is in `job_queue.py` (the queue) and `worker.py` (the processor). `main.py` runs a simulation you can use to reproduce the issues.

Find the root causes and fix them. Do not change the public method signatures.
