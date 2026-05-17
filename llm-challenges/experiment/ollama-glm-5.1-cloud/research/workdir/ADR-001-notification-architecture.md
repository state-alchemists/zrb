# ADR 001 — Notification Subsystem Message Broker

- **Status**: Proposed
- **Date**: 2026-05-17
- **Deciders**: Backend team (3 senior, 3 mid-level engineers)
- **Context tags**: notifications, messaging, reliability, scaling

## Context

Our SaaS project management platform (85K MAU, ~2M tasks/month, peak ~500 req/s) handles all notifications — emails, webhooks, and soon WebSocket pushes — synchronously inside the HTTP request cycle. This has caused request timeouts (avg 800 ms, spikes to 8 s), silent delivery failures with no retry or dead-letter queue, two cascading-failure incidents from slow webhook endpoints exhausting the connection pool, and zero delivery guarantees for billing-critical notifications that require exactly-once delivery.

We need to decouple notification production from the HTTP path, add retry with exponential backoff, guarantee at-least-once delivery (exactly-once for billing events), support WebSocket push within two quarters, and absorb 10x traffic growth without re-architecting.

Hard constraints: 6-person team with no dedicated infrastructure engineer, no Kafka experience, an existing Redis instance in production (session storage, rate limiting), a 2-week window before the solution must deliver value, and a modest budget that rules out managed Confluent Cloud at scale.

## Decision

> We will use Redis Streams as the message broker for the notification subsystem.

Redis Streams is the pragmatic choice because it satisfies every requirement within our constraints: we already operate Redis in production, the team has institutional knowledge of its failure modes and operational procedures, and adding consumer-group-based stream processing to the existing instance is an incremental change — not the introduction of an entirely new distributed system. Our throughput ceiling even at 10x growth (~5,000 notifications/s sustained) is well within a single Redis node's capability (100K+ entries/s), so we gain no benefit from Kafka's horizontal-partitioning strengths. The 2-week time-to-value constraint is the deciding factor: a team with zero Kafka experience cannot responsibly stand up and harden a Kafka cluster in that window, whereas the Redis Streams implementation path — `XADD` on produce, `XREADGROUP` + `XACK` on consume — is approachable in days.

For exactly-once billing notifications, Redis Streams provides at-least-once delivery natively. We achieve exactly-once semantics at the application layer by persisting a deduplication key (e.g., `notif:{event_id}:{recipient}`) in PostgreSQL before acknowledging the message, and making the notification-sending handler idempotent — check key existence, send if absent, mark delivered. This is the same deduplication pattern required even with Kafka transactions when the downstream system (email provider, webhook endpoint) is not transactional, which it never is in our case.

## Consequences

### Positive

- **Fastest path to value.** Incremental addition to existing Redis — no new infrastructure to provision, monitor, or learn to operate. First async notification can ship within days, well inside the 2-week window.
- **Lower operational burden.** One fewer distributed system to run. No broker election, partition rebalancing, ZooKeeper/KRaft quorum tuning, or ISR monitoring. Our 6-person team with no dedicated infra engineer can maintain this.
- **No new budget line item.** Redis is already paid for. Self-managed Kafka clusters require minimum 3 brokers plus ZooKeeper/KRaft nodes on appropriately sized hardware; managed alternatives are ruled out by budget.
- **Sufficient throughput and ordering.** Per-stream entry-ID ordering guarantees notifications for a given entity are processed in sequence. Single-node throughput of 100K+ entries/s gives us 20x headroom over our 10x growth target.
- **Consumer groups built-in.** `XGROUP`, `XREADGROUP`, `XACK`, and `XPENDING` provide the consumer-group semantics we need for parallel workers, retry tracking, and dead-letter detection without external coordination.
- **WebSocket-friendly.** Redis Pub/Sub already powers real-time patterns; Streams add durable, replayable message history that Pub/Sub lacks. The same Redis instance serves both push and durable-queue use cases.

### Negative

- **No native exactly-once semantics.** Redis Streams delivers at-least-once. Exactly-once for billing notifications requires application-level deduplication (PostgreSQL idempotency table). This adds implementation complexity and a cross-system dependency that must be tested carefully.
- **Memory-bound retention.** Redis holds stream data in memory. We must set `MAXLEN` policies (e.g., `XADD stream MAXLEN ~ 100000 * field value`) to cap memory growth and periodically trim. Long-term audit trails must be persisted to PostgreSQL — the stream is a queue, not a store of record.
- **Single-node availability risk.** Our current Redis deployment is a single instance (or a simple primary-replica pair). Unlike Kafka's multi-broker replication, a Redis primary failure means brief unavailability until replica promotion. We should enable Redis Sentinel or enable Amazon ElastiCache Multi-AZ before going to production with Streams.
- **Limited partitioning.** Redis Streams do not support Kafka-style partitioned topic parallelism. If we ever need multiple consumers reading different shards of the same logical stream for throughput, we must manually shard into multiple stream keys. At our projected scale this is unnecessary, but it means the architecture does not auto-scale partition parallelism.
- **Monitoring maturity.** Kafka ecosystems (Burrow, Kafka Manager, Confluent Control Center) provide deep consumer-lag dashboards. Redis Stream lag (via `XPENDING` and `XINFO`) is more rudimentary. We will need to build custom monitoring for pending-entry counts and consumer health.

### Follow-ups

- Implement the idempotency-key deduplication table in PostgreSQL for billing notification exactly-once guarantees.
- Configure `MAXLEN` trimming on all notification streams; define retention policy and archiving to PostgreSQL.
- Enable Redis Sentinel or ElastiCache Multi-AZ for high availability before production launch.
- Build a `XPENDING`-based consumer-lag dashboard and alert (e.g., pending count > threshold for > N minutes triggers PagerDuty).
- Design the dead-letter stream pattern: after N retries with exponential backoff, `XADD` to a `notifications:dead-letter` stream and alert.

## Alternatives Considered

- **Apache Kafka** — Rejected. Kafka's strengths — multi-broker fault tolerance, per-partition parallelism, native transactional exactly-once, and long-term log retention — are real, but none of them map to our current constraints. Our throughput is 3 orders of magnitude below Kafka's design target. Our team has zero Kafka operational experience and no dedicated infrastructure engineer, making self-managed Kafka a reliability risk; two Kafka-related outages in the first year would be more damaging than the incidents we are trying to fix. Managed Kafka (Confluent Cloud, Amazon MSK) removes the operational burden but exceeds our budget at projected scale. Most critically, responsible Kafka adoption — cluster design, security, monitoring, consumer group tuning, partition strategy — takes 4–8 weeks for an experienced team, far exceeding our 2-week time-to-value constraint. We would choose Kafka if our throughput requirement exceeded ~50K sustained messages/s, if we needed multi-service event sourcing with long retention windows, if we had a dedicated platform team, or if the budget accommodated a managed offering.