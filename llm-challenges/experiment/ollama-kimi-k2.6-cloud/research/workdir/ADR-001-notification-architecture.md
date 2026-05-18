# ADR-001 — Notification Subsystem Architecture

**Status**: Proposed

## Context

Our Python/Flask monolith handles notifications (emails, webhooks) synchronously inside the HTTP request cycle. At 85,000 monthly active users and peak loads of ~500 req/s, this has produced:

- Average notification latency of 800 ms, spiking to 8 s during peak hours.
- Silent drops when downstream providers fail, with no retry or dead-letter mechanism.
- Two production incidents this year where a slow webhook endpoint caused connection pool exhaustion and cascading failures.
- No delivery guarantees for billing-critical events ("trial expired", "payment failed").

We must decouple notification dispatch from the request cycle, add retry with exponential backoff, guarantee at-least-once delivery for all events, and achieve exactly-once semantics for billing notifications. We also expect to add real-time WebSocket push within two quarters and must support 10× traffic growth (~5,000 req/s peak) without a second re-architecture.

Our constraints are stiff:

- Engineering team of six (three senior, three mid-level), with **no dedicated infrastructure engineer**.
- Redis already runs in production for sessions and rate limiting.
- **No Kafka experience** on the team.
- Value must be delivered within **two weeks** of starting the migration.
- Budget is modest; managed Confluent Cloud is not affordable at target scale.

## Decision

**We will use Redis Streams as the backing log for the notification subsystem.**

This choice prioritizes operational fit and time-to-value over the theoretical ceiling throughput of Kafka. Redis Streams provides FIFO ordering per stream, native consumer groups with automatic pending-entry reclaiming, and throughput in the hundreds of thousands of messages per second per node—well above our 5,000 req/s peak target. Because Redis is already in production, we avoid introducing a new runtime, new failure modes, and new operational runbooks. The migration can be completed incrementally inside the two-week window by adding stream producers to the existing Flask app and deploying lightweight consumers on the same compute fleet.

For billing-critical notifications, we will implement **effectively-once** semantics on top of Redis Streams' at-least-once delivery. Consumers will deduplicate using an idempotency key stored in a Redis SET with a 24-hour TTL. Acknowledgement of the stream entry and recording of the idempotency key will be wrapped in a Redis transaction (Lua script or `MULTI`/`EXEC`) to eliminate double-processing races. This pattern is robust, team-comprehensible, and easier to audit than Kafka's transactional exactly-once semantics, which still require idempotent application logic to be truly safe.

## Consequences

### Positive

- **Operational simplicity**: The team already monitors, backs up, and tunes Redis. Adding a Streams use-case does not require new infrastructure, new deployment artifacts, or new vendor contracts.
- **Speed to value**: A working producer/consumer pair can be deployed in days. The two-week deadline is achievable because the skills and tooling are already in place.
- **Throughput headroom**: Redis Streams can sustain >100,000 messages/sec per node. Our 10× target of 5,000 req/s leaves enormous headroom.
- **Consumer groups**: Redis 5.0+ consumer groups provide automatic partitioning, failure detection, and message reclaiming when consumers crash. This gives us the reliability primitives we need without external coordination services such as ZooKeeper.
- **Ordering guarantees**: Per-stream FIFO ordering is sufficient. Because each notification type (email, webhook, billing) will use its own stream, ordering within a category is preserved.
- **WebSocket synergy**: Redis Streams can feed a future WebSocket push service directly, or coexist with Redis Pub/Sub for real-time broadcasting, keeping our messaging layer unified.
- **Cost**: Zero additional infrastructure spend at current and projected scale.

### Negative

- **Memory-bound retention**: Unlike Kafka's disk-backed log, Redis Streams are memory-first. We must enforce retention aggressively (e.g., `MAXLEN` of 50,000 per stream, or time-based eviction) to prevent Out-of-Memory events. Long-term audit trails will be offloaded to S3 or PostgreSQL by a background archival consumer.
- **Exactly-once is application-level**: Redis Streams does not offer broker-level exactly-once semantics. We accept the burden of deduplication logic in consumers. A bug in that logic could duplicate a billing email.
- **Ecosystem maturity**: Kafka has a richer ecosystem of connectors, stream-processing frameworks (Kafka Streams, ksqlDB), and third-party monitoring integrations. If our needs evolve toward complex stream processing, we may outgrow Redis Streams and need to revisit this decision.
- **Horizontal scaling limits**: While a single Redis primary handles our target comfortably, scaling beyond one primary for Streams requires client-side sharding or a Redis Cluster migration. That is acceptable for our 10× horizon but becomes a constraint if we grow 100×.

## Alternatives Considered

### Apache Kafka

Kafka was rejected because its operational complexity is incompatible with our team size and timeline.

- **Operational burden**: Self-hosting Kafka requires a broker cluster plus ZooKeeper or KRaft controllers, careful tuning of replication factors, ISR management, and partition rebalancing. With no dedicated infrastructure engineer and no prior Kafka experience, the operational risk of a self-managed cluster is unacceptably high.
- **Time to production**: A production-grade Kafka deployment—including security hardening, monitoring, consumer group testing, and failover drills—cannot be completed safely within two weeks by a team learning the technology for the first time.
- **Cost**: Managed Confluent Cloud would solve the operational problem but is explicitly out of budget at scale.
- **Exactly-once semantics**: Kafka offers idempotent producers and transactions, but exactly-once is still opt-in, requires careful producer/consumer configuration, and does not eliminate the need for idempotent application logic. Given that we would still need to write deduplication code, the marginal guarantee over Redis Streams does not justify the infrastructure cost.

Kafka would become the right choice if our throughput requirements exceeded 100,000 messages/sec, if we needed months of durable log retention for compliance, or if we had dedicated platform engineering capacity to operate the cluster. None of those conditions apply today.
