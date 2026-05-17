# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context
The current notification system is synchronous, causing request timeouts (up to 8s spikes), silent failures during provider downtime, and cascading failures due to connection pool exhaustion. We need a decoupled, asynchronous architecture that supports:
- Retries with exponential backoff.
- At-least-once delivery for general notifications and exactly-once semantics for billing-critical events.
- Real-time WebSocket integration in the near future.
- Scalability for 10x current traffic (up to 5,000 req/s peak).

**Constraints:**
- Team: 6 engineers (no dedicated infra/DevOps), no prior Kafka experience.
- Infrastructure: AWS, already running Redis for sessions/rate-limiting.
- Timeline: < 2 weeks for initial value delivery.
- Budget: Modest; managed Kafka (Confluent) is currently cost-prohibitive.

## Decision
We will use **Redis Streams** as the backbone for the notification subsystem.

**Justification:**
1. **Operational Simplicity**: Redis is already in our production stack. Leveraging it avoids the overhead of deploying and managing a new Zookeeper/Kafka cluster, fitting within the 2-week delivery window and the limited engineering bandwidth.
2. **Performance**: At 500-5,000 req/s, Redis Streams easily handles the throughput requirements with sub-millisecond latency.
3. **Consumer Groups**: Redis Streams provide consumer groups, allowing us to distribute notification processing across multiple workers and track offsets, ensuring no message is lost.
4. **Retention and Recovery**: While not as durable as Kafka, Redis Streams allow for message retention and playback from specific IDs, enabling the necessary retry logic and dead-lettering via custom scripts or side-streams.
5. **Exactly-Once Semantics**: By combining Redis's atomic operations with an idempotency key stored in PostgreSQL (already the source of truth for billing), we can achieve effectively exactly-once delivery for critical billing events without the complexity of Kafka's transactional producers.
6. **Future Proofing**: Redis's pub/sub capabilities blend naturally with the planned WebSocket push notifications.

## Consequences
### Pros
- **Zero New Infra**: No additional server types or complex JVM tuning required.
- **Rapid Deployment**: Implementation can begin immediately using existing client libraries.
- **Low Latency**: Extremely fast enqueue/dequeue operations.
- **Resource Efficiency**: Shares the existing Redis memory footprint, reducing AWS costs.

### Cons
- **Memory Bound**: Unlike Kafka (disk-based), Redis is primarily memory-bound. We must implement aggressive stream capping (`MAXLEN`) to prevent OOM.
- **Lower Durability**: In the event of a total Redis crash, there is a higher risk of data loss compared to Kafka's distributed commit log, unless AOF (Append Only File) is tuned for maximum safety, which may impact performance.
- **Manual DLQ**: Dead-letter queues must be implemented manually (e.g., moving failed messages to a separate "failed-notifications" stream) rather than using native Kafka DLQ patterns.

## Alternatives Considered
### Apache Kafka
Rejected for the following reasons:
- **Operational Complexity**: Kafka requires significant expertise to manage (partitions, replication factors, Zookeeper/KRaft). With no dedicated infra engineer and no internal Kafka experience, the risk of misconfiguration causing production instability is too high.
- **Overkill for Scale**: Kafka is designed for millions of events per second. Our 10x growth target (~5k req/s) is well within the capabilities of a well-tuned Redis instance.
- **Deployment Timeline**: Setting up a production-grade, highly available Kafka cluster would exceed the 2-week window for delivering initial value.
- **Cost**: Self-hosting requires more expensive instances (high disk/RAM); managed options exceed the current budget.
