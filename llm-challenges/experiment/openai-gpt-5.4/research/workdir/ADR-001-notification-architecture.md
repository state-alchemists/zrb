# Title

ADR-001: Use Redis Streams for the Notification Subsystem

# Status

Proposed

# Context

The current notification subsystem runs synchronously inside the Flask HTTP request cycle. This is causing high latency, request timeouts, silent delivery failures, and cascading failures when downstream email or webhook providers are slow or unavailable. The system must move notification processing out of the request path and support retries, backoff, and failure isolation.

The platform currently serves about 85,000 monthly active users, processes roughly 2 million tasks per month, and sees peak traffic around 500 requests per second. The target is to support 10x traffic growth, add WebSocket push notifications within two quarters, and improve delivery guarantees for billing-critical events.

The main constraints are operational and organizational as much as technical. The engineering team is six people with no dedicated infrastructure engineer. Redis is already running in production for sessions and rate limiting, while the team has no Kafka experience today. The solution must deliver value within two weeks, fit a modest budget, and preserve exactly-once semantics for billing notifications where required.

Two options were evaluated for the notification backbone: Apache Kafka and Redis Streams.

# Decision

Choose Redis Streams as the notification subsystem backbone.

Redis Streams is the better fit for the current stage of the system because it solves the immediate architectural problem with the lowest operational cost and the fastest time to production. It provides the core capabilities this subsystem needs now: asynchronous decoupling from the request cycle, durable stream-based queues, consumer groups for horizontal workers, replay of pending messages, and explicit acknowledgment semantics that support at-least-once processing.

For expected notification volume, Redis Streams throughput is sufficient. Even with 10x growth, this workload is still modest compared with what Redis can handle for stream append and consumer-group reads, especially since the current peak is only about 500 requests per second and not every request emits a notification. Ordering guarantees are also adequate: Redis Streams preserve message order within a stream, which is enough if we partition by notification type or aggregate key where ordering matters.

Kafka is stronger on raw throughput, long-term retention, partition-scaled ordering, and mature event-streaming semantics, but those advantages are not the bottleneck in this system today. The bigger risk is operational complexity. Running Kafka well requires broker sizing, partition planning, replication tuning, retention management, monitoring, and on-call expertise the team does not currently have. Given the two-week delivery constraint and modest budget, Kafka would likely delay value and increase incident risk.

Exactly-once semantics for billing notifications should not be delegated to the broker alone. In practice, exactly-once for external side effects such as email and webhooks requires application-level idempotency, a durable notification record in PostgreSQL, and idempotency keys passed to downstream providers where supported. Redis Streams supports this design well enough: the system can write a billing notification record transactionally in PostgreSQL, publish the event to the stream, and have workers perform idempotent sends with deduplication based on a stable event identifier. This achieves exactly-once effect where feasible, while the transport itself remains at-least-once.

In short, Redis Streams is the right decision because it meets the required delivery model, integrates with existing infrastructure, keeps setup and migration within the team’s capacity, and leaves room to add WebSocket notification consumers later without introducing Kafka’s operational burden.

# Consequences

Pros:
- Fastest path to decoupling notifications from HTTP requests because Redis already exists in production.
- Lower operational complexity than Kafka; feasible for a six-person team without a dedicated infrastructure engineer.
- Consumer groups provide horizontal scaling for workers and support pending-entry recovery when consumers fail.
- Sufficient throughput for current load and realistic 10x growth in the notification domain.
- Stream retention can be configured to keep enough history for retries, debugging, and short-term replay.
- Easy to extend with additional consumers later, including a WebSocket push worker.
- Lower cost than introducing a separately operated Kafka cluster.

Cons:
- Weaker durability and retention model than Kafka for long-lived event history; Redis Streams is not ideal as a system-of-record event log.
- Exactly-once semantics are not provided by Redis Streams itself; the application must enforce idempotency and deduplication.
- Ordering guarantees are stream-local and less flexible than Kafka partition ordering at large scale.
- Retry scheduling and dead-letter handling may require additional application logic or supporting data structures.
- Sharing the same Redis deployment with sessions, rate limiting, and notifications can create resource contention unless isolated by instance, database, or capacity planning.

# Alternatives Considered

## Apache Kafka

Kafka was rejected for now because it is a stronger platform than this problem currently requires, and its operational cost is misaligned with the team’s constraints.

Kafka’s strengths are real: very high throughput, durable replicated logs, configurable long retention, consumer groups at scale, partition-based ordering, and stronger support for exactly-once stream processing within the Kafka ecosystem. If this were a large event-driven platform with multiple independent downstream systems, high fan-out analytics consumers, or a team already experienced with Kafka operations, it would be a compelling choice.

However, those benefits do not outweigh the costs in this context. The team has no Kafka experience, no dedicated infrastructure engineer, a hard two-week time-to-value limit, and a modest budget that rules out the easiest managed Kafka option. Self-managing Kafka on AWS would add meaningful operational overhead immediately. Kafka would also be excessive for the current notification workload, which is moderate and can be handled by Redis Streams without re-architecting the whole system.

Kafka also does not eliminate the need for application-level idempotency for billing notifications. Although Kafka supports exactly-once semantics for producer and stream-processing workflows, end-to-end exactly-once delivery to external email and webhook providers still requires deduplication and idempotent side-effect handling in the application. That means Kafka’s strongest semantic advantage does not fully solve the hardest requirement here.

For these reasons, Kafka should be reconsidered only if the notification subsystem evolves into a broader event backbone with much higher throughput, longer retention requirements, many heterogeneous consumers, or dedicated platform engineering support.
