# Title
Notification Subsystem Event Backbone: Redis Streams vs Apache Kafka

# Status
Proposed

# Context
The current notifier runs synchronously in the Flask HTTP request cycle and is causing (1) request timeouts (p95 spikes to seconds), (2) silent drops when downstream providers/webhook endpoints fail, and (3) cascading failures (slow webhooks exhausting connection pools and impacting unrelated features). We must decouple notification delivery from request handling and add:

- Asynchronous processing
- Retry with exponential backoff and a dead-letter path
- At-least-once delivery for most notifications
- Exactly-once semantics for billing-critical notifications ("trial expired", "payment failed")
- A path to real-time WebSocket push notifications within ~2 quarters
- Capacity to handle ~10x traffic growth without a full re-architecture

Constraints:

- Team of 6 engineers, no dedicated infra engineer
- Redis already runs in production (sessions/rate limiting)
- No Kafka experience today
- Must deliver value within ~2 weeks of setup/migration
- Modest budget; cannot rely on Confluent Cloud at full scale

Key technical properties to evaluate:

- Throughput and scalability headroom
- Ordering guarantees (per key/partition vs global)
- Message retention and replay
- Consumer groups and fan-out behavior
- Exactly-once semantics (broker-level vs application-level)
- Operational complexity (day-2 ops, upgrades, monitoring, on-call burden)

# Decision
Adopt **Redis Streams** as the notification subsystem backbone, using **consumer groups** for worker scaling, and implement **application-level exactly-once** for billing notifications via an idempotency/deduplication key stored in PostgreSQL.

Justification:

- **Fastest time-to-value under the 2-week constraint**: Redis is already operated in production; adding Streams and worker processes is a smaller incremental change than introducing Kafka (new cluster, new operational playbooks, new client semantics).
- **Operational fit for a small team**: Redis (even with Streams) is significantly simpler to run and monitor than Kafka on AWS without a dedicated infra owner. Kafka’s operational surface (brokers, controllers, partitions, rebalancing, storage, compaction/retention tuning) increases on-call risk.
- **Meets near-term scale**: With peak ~500 req/s today and a 10x target, Redis Streams can support high throughput for a notification workload if we keep payloads small (store large bodies in Postgres/S3) and scale consumers horizontally via consumer groups.
- **Ordering and consumer groups sufficient for notifications**: Redis Streams preserve order within a stream (ID order). For notifications we typically need ordering per entity (task/user/billing account), not global ordering. We will route by topic/stream (and optionally by key sharding across multiple streams) to preserve per-key ordering while allowing parallelism.
- **Exactly-once “where feasible” is realistically application-level anyway**: Kafka’s “exactly-once semantics” (EOS) is primarily for Kafka-to-Kafka transactional processing. Our critical side effects are external (email/webhook/payment provider); true exactly-once delivery cannot be guaranteed end-to-end with either system. The correct approach is **idempotent side effects + deduplication**. Redis Streams supports at-least-once delivery; we will add a durable idempotency record in Postgres to achieve exactly-once *effects* for billing notifications.
- **WebSocket push compatibility**: Streams can feed a push service (e.g., a WebSocket gateway) similarly to Kafka. We can add a dedicated consumer group for real-time push without impacting email/webhook workers.

# Consequences
## Pros
- **Low operational complexity**: Reuses existing Redis footprint and team knowledge; fewer moving parts than Kafka.
- **Rapid implementation**: Stream producer in the monolith + worker consumers can be delivered quickly, meeting the 2-week requirement.
- **Consumer groups built-in**: Horizontal scaling via `XGROUP`/`XREADGROUP`, with per-message acknowledgements (`XACK`) enabling at-least-once processing.
- **Good throughput for the workload**: Redis is memory-first and can handle high message rates for modest payload sizes; suitable for notification events.
- **Natural backpressure**: Pending Entries List (PEL) + consumer lag metrics provide a clear signal for scaling workers.

## Cons
- **We must implement reliability patterns ourselves**: Retries with exponential backoff and DLQ are not “first-class” like some Kafka ecosystems; we will implement delayed retries (e.g., retry streams + scheduled requeue using sorted sets or a dedicated delay mechanism) and a dead-letter stream.
- **Retention/replay is more limited than Kafka**: Streams can retain by maxlen/time, but long-term replay and audit-style retention is less ergonomic and more costly in Redis memory. If we later need multi-day/month replay, we may need to offload to Postgres/S3 or revisit Kafka.
- **Exactly-once is not broker-provided**: Redis Streams provides at-least-once; exactly-once for billing requires application-level deduplication and idempotent handlers.
- **Scaling beyond a single Redis node requires careful design**: Redis Cluster and Streams work, but cross-slot considerations and operational tuning can get tricky. We may need sharded streams (e.g., `notif:{shard}`) to scale write throughput and preserve ordering constraints.

# Alternatives Considered
## Apache Kafka (Rejected)
Kafka is a strong event backbone with excellent scalability and mature tooling, but it is rejected for this phase due to fit with constraints:

- **Operational complexity / team constraints**: Running Kafka reliably on AWS without managed Confluent and without an infra engineer is a significant burden (capacity planning, broker storage, partitioning strategy, upgrades, rebalancing, monitoring, incident response).
- **Longer setup/migration time**: Standing up Kafka (or MSK), securing it, wiring producers/consumers, and establishing operational runbooks is unlikely to fit within the “deliver value in 2 weeks” requirement.
- **Exactly-once does not solve our hardest problem**: Kafka EOS applies to transactional read-process-write within Kafka. Our critical actions (sending emails, calling webhooks) are external side effects. End-to-end exactly-once still requires idempotency/deduplication logic at the application boundary, so Kafka does not eliminate this requirement.
- **Budget constraint**: A robust Kafka deployment (especially managed) can be costly at scale; self-managed reduces spend but increases operational risk—both are poor fits for the current budget and staffing.

Kafka remains a viable future upgrade path if we outgrow Redis Streams on retention/replay requirements, need very large fan-out with long retention, or require a broader event platform beyond notifications.
