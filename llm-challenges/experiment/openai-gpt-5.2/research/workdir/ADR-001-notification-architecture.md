# Title
Notification Subsystem Messaging Backbone (Kafka vs Redis Streams)

# Status
Proposed

# Context
We run a SaaS project management platform (85k MAU, ~2M tasks/month, peak ~500 req/s) on a Python/Flask monolith with PostgreSQL and four web servers on AWS. Notifications (email + webhooks) are currently executed synchronously in the HTTP request path, which has led to:

- High and spiky request latency (avg ~800ms, spikes to ~8s)
- Silent drops when providers/endpoints are down (no retry/DLQ)
- Cascading failures (slow webhooks exhausting connection pools)
- A strict requirement that billing-critical notifications (e.g., “trial expired”, “payment failed”) be delivered **exactly once** (or as close as feasible) and non-billing notifications at least once.

Scaling targets / near-term roadmap:

- Decouple notification delivery from request cycle (async workers)
- Retries with exponential backoff and dead-lettering
- Add real-time WebSocket push notifications within ~2 quarters
- Support ~10× traffic growth without needing to replace the messaging backbone

Constraints:

- Team of 6, no dedicated infra engineer
- Redis is already in production; the team has no Kafka experience
- Must deliver value with no more than ~2 weeks setup/migration
- Modest budget; cannot rely on Confluent Cloud at full scale

Decision needed: choose the messaging/event backbone for the notification subsystem between **Apache Kafka** and **Redis Streams**.

# Decision
Choose **Redis Streams** as the notification subsystem backbone.

Justification:

1. **Time-to-value and operational fit (team/budget constraints):** We already operate Redis and can extend it to Streams with minimal new operational surface area. Kafka (especially self-managed) introduces significant operational complexity (brokers, partitions, replication, monitoring, upgrades, capacity planning) and a higher learning curve, which conflicts with the “≤2 weeks to deliver value” requirement and lack of Kafka experience.

2. **Throughput and scalability for our workload:** Current peak is ~500 req/s; even at 10× growth (~5k req/s), Redis Streams can handle this class of throughput on appropriately sized instances, especially if we keep message payloads small and store large bodies in PostgreSQL/S3. Kafka can scale far beyond this, but the incremental capability is not currently the limiting factor.

3. **Consumer groups and ordering guarantees:** Redis Streams provides consumer groups with at-least-once delivery and per-stream ordering; within a stream, messages are ordered by stream ID. This is sufficient for notification processing when combined with keying strategy (e.g., separate streams per notification type or per tenant/account where ordering matters). Kafka offers stronger/clearer ordering per partition and better tooling around partitioning, but we can meet requirements with Redis Streams now.

4. **Retention and replay requirements:** Kafka excels at long retention and replay (log as source of truth). For notifications, we primarily need bounded retention for retry/DLQ and short-term replay during incidents. Redis Streams supports trimming (MAXLEN) and explicit archival (persist failed payloads in PostgreSQL and keep a DLQ stream), which satisfies our operational needs without turning the stream into a long-lived event store.

5. **Exactly-once semantics for billing notifications:** Neither Kafka nor Redis Streams provides true end-to-end exactly-once for external side effects (email/webhooks) without application-level idempotency. Kafka can provide exactly-once *processing* semantics for Kafka-to-Kafka pipelines using transactions and idempotent producers, but once we call external providers, exactly-once still requires deduplication/idempotency keys. With Redis Streams, we will implement exactly-once for billing notifications via:
   - An **outbox pattern** in PostgreSQL (transactionally record billing notification intent with a unique idempotency key)
   - A publisher that reads the outbox and appends to the stream
   - Worker-side deduplication using the same idempotency key (e.g., a `notifications_delivered` table with a unique constraint)
   - Idempotency keys passed to email/webhook providers where supported

Given our constraints, Redis Streams plus application-level idempotency/outbox delivers required guarantees with much lower operational risk than Kafka.

# Consequences
## Pros
- **Fast adoption:** Minimal new infrastructure; leverages existing Redis footprint and operational knowledge.
- **Decouples HTTP from delivery:** Workers consume from Streams asynchronously, eliminating request timeouts from notification sending.
- **At-least-once delivery with consumer groups:** Pending Entries List (PEL) enables retries and recovery if a consumer crashes.
- **Simpler retry/DLQ implementation:**
  - Use exponential backoff by re-enqueueing with a delay mechanism (e.g., sorted set scheduler or separate “delayed” stream) and a DLQ stream after max attempts.
- **Lower operational complexity than Kafka:** Fewer moving parts, easier to monitor for a small team without a dedicated infra engineer.
- **Good fit for WebSocket push:** Streams can act as a fan-out source for near-real-time push workers; short retention is acceptable for ephemeral push.

## Cons
- **Weaker “log as system of record” story:** Redis Streams is not a substitute for Kafka’s durable, long-retained, replayable log. Long-term audit/replay must live in PostgreSQL (outbox/event tables) if needed.
- **Scaling limitations vs Kafka:** Redis is single-primary per shard; scaling is typically vertical or via Redis Cluster sharding, which can be operationally tricky. Kafka scales more naturally with partitions across brokers.
- **Ordering constraints require careful design:** Ordering is per stream; achieving strict per-entity ordering at high scale may require multiple streams or consistent routing strategy.
- **Exactly-once still needs application logic:** Must implement outbox + idempotency/dedup, and rigorously test for race conditions.
- **Backpressure and large payloads:** Must keep messages small; store large payloads elsewhere and reference by ID.

# Alternatives Considered
## Apache Kafka (rejected)
Kafka is a strong choice for high-throughput event streaming with durable retention, robust consumer groups, partition-based ordering, and mature tooling. It would also support future evolution toward an event-driven architecture.

Reasons for rejection given current constraints:

- **Operational complexity and setup time:** Self-managing Kafka (even with KRaft) involves broker sizing, partitions/replication factor decisions, monitoring (lag, ISR health), upgrades, and incident response. With no Kafka experience and no infra engineer, this is unlikely to fit the “≤2 weeks to deliver value” requirement.
- **Budget mismatch for managed offerings:** Confluent Cloud (or equivalent managed Kafka) reduces ops burden but is explicitly unaffordable at full scale today.
- **Exactly-once is not end-to-end for our use case:** Kafka transactions/idempotent producers help within Kafka pipelines, but notification delivery to external email/webhook endpoints still requires application-level idempotency/deduplication. This reduces the practical benefit of Kafka’s exactly-once features for our most critical requirement.

Kafka remains a viable future upgrade if we later need multi-day retention/replay, cross-service eventing at scale, or higher throughput beyond Redis’s comfortable operating envelope.
