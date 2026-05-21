# ADR-001: Notification Subsystem — Asynchronous Message Broker

**Status:** Proposed

---

## Context

We operate a SaaS project management platform (85k MAU, ~2M tasks/month, peak 500 req/s). Notifications (emails + webhooks for task updates, assignments, and billing events) are sent synchronously inside the HTTP request cycle, causing three concrete production issues:

1. **Request timeouts** — average 800 ms, spikes to 8 s at peak.
2. **Silent failures** — email or webhook provider outages drop notifications without retry or dead-letter queue.
3. **Cascading failures** — slow webhook endpoints have caused PostgreSQL connection pool exhaustion twice this year.

We must decouple notification delivery from the request cycle with an asynchronous message broker. The subsystem must provide:

- **Async processing** — push notification work onto a queue, return the HTTP response immediately.
- **Retry with exponential backoff** — transient failures must be retried automatically.
- **At-least-once delivery for billing events**, with exactly-once semantics where feasible.
- **A path to WebSocket push notifications** within two quarters.
- **Headroom for 10x traffic growth** (peak ~5k req/s) without a re-architecture.

**Team constraints:** 6 engineers (3 senior, 3 mid-level), no dedicated infrastructure engineer, no Kafka experience on the team, modest budget (managed Confluent Cloud is out of scope), and a 2-week window from decision to delivering measurable value. We already run Redis in production for session storage and rate limiting.

---

## Decision

**Adopt Redis Streams as the notification message broker.**

Redis Streams will replace the synchronous notification path. The HTTP request handler will `XADD` a notification event to a stream; a background worker (consumer group) will `XREADGROUP` events, deliver them, and `XACK` on success. Failed deliveries go to a retry stream with exponential backoff via `XCLAIM` and `XPENDING`. Billing notifications carry an idempotency key tracked in PostgreSQL, providing exactly-once delivery semantics at the application level.

---

## Consequences

### Benefits

- **Zero new infrastructure.** Redis is already provisioned, monitored, and operated in production. We add a stream, not a cluster.
- **Fast time-to-value.** The team knows Redis. A working async notification pipeline can ship within the 2-week setup window — days, not weeks.
- **Sufficient throughput.** Redis Streams handles well beyond our 10x target (5k req/s). Benchmarks on modest hardware sustain 100k+ messages/s with sub-millisecond latency. Kafka's millions-per-second throughput is unnecessary overhead at our scale.
- **Consumer groups with PEL (Pending Entry List).** Redis Streams provides exactly the primitives we need: `XREADGROUP` for load-balanced consumers, `XPENDING` to detect stalled deliveries, and `XCLAIM` to transfer unacknowledged messages to another consumer for retry.
- **Natural fit for WebSocket push.** Redis Pub/Sub (already available in the same Redis instance) can fan out real-time notifications to WebSocket servers. We can bridge streams to Pub/Sub with a small consumer, keeping the push path in the same operational domain.
- **Low operational burden.** A single Redis instance (or a small Redis Cluster) is manageable by a 6-person team with no infra specialist.

### Trade-offs

- **No native exactly-once semantics.** Redis Streams is at-least-once by design. We must implement consumer-side deduplication (idempotency keys in PostgreSQL) for billing notifications. This is achievable but requires discipline — the broker alone won't enforce it.
- **Memory-bound retention.** Kafka persists messages to disk with configurable retention (days/weeks). Redis Streams keeps data in memory (with optional RDB/AOF persistence). Large retention windows require more RAM or explicit stream trimming (`XTRIM` or `MAXLEN`). For our use case (notifications consumed within minutes), this is not a problem — we trim aggressively.
- **Manual sharding at scale.** Redis Streams consumer groups assume a single stream. Sharding across multiple streams (for extremely high throughput beyond our target) requires application-level partitioning — Kafka does this transparently. At 10x (5k req/s) this is not a concern; at 100x it would be.
- **Smaller ecosystem.** Kafka has richer tooling (Kafka Connect, Schema Registry, KSQL) for streaming ETL. Redis Streams has `redis-cli` and client libraries. We don't need the ecosystem today, and adding it later via Kafka Connect bridging is a valid escape hatch.

---

## Alternatives Considered

### Apache Kafka (Rejected)

Kafka is the industry-standard event broker and excels at high-throughput, long-retention, exactly-once workloads. It was rejected for the following reasons specific to our constraints:

- **Operational complexity.** A production Kafka deployment requires at least 3 broker nodes + ZooKeeper (or KRaft) + monitoring (JMX, Cruise Control). Our 6-person team has no Kafka experience and no dedicated infrastructure engineer. The learning curve and operational tax would absorb the entire team for weeks.
- **Exceeds our throughput needs by orders of magnitude.** Kafka is designed for millions of messages per second. Our 10x target is 5k req/s. The operational cost-to-benefit ratio is deeply unfavorable — we pay the full complexity premium for capability we will not use.
- **Overkill for the 2-week delivery constraint.** Standing up a production Kafka cluster, configuring topic partitioning, tuning producer/consumer settings, and teaching the team Kafka's consumer group protocol (offsets, rebalancing, `__consumer_offsets` topics) cannot credibly fit within 2 weeks for a team new to the technology.
- **New infrastructure = new attack surface.** Kafka introduces JVM heap tuning, disk I/O patterns, partition leader election, and ISR (in-sync replica) management — failure modes our team has never debugged. Redis failure modes (memory pressure, replication lag) are already understood.
- **Budget tension.** Self-hosted Kafka at our scale needs 3–5 m6i.large or similar instances (~$300–500/month). Managed Confluent Cloud starts at higher tiers. Redis Streams imposes zero additional infrastructure cost — we use the existing Redis instance.

The one genuine advantage Kafka holds over Redis Streams — native exactly-once semantics via transactions + idempotent producer — does not justify the cost. We can achieve exactly-once delivery for billing notifications with application-level idempotency keys (a well-understood pattern in any language), and we get it for free in terms of infrastructure.

### Keep the synchronous path (Rejected)

Continuing to send notifications inline in the HTTP request cycle is the status quo. It directly caused the three production incidents described in Context. The only remediation is decoupling — which requires a queue.

---

## Implementation Sketch

The transition plan fits within the 2-week constraint:

1. **Week 1 — Core pipeline (3 engineers):**
   - Producer helper (`xadd_notification`) pushed into the Flask app. Request handlers call it instead of sending notifications synchronously. The original notification logic is moved into a consumer function.
   - Consumer script (`python -m workers.notifications`) using `XREADGROUP` with `BLOCK`. On success: `XACK`. On transient failure: leave PEL entry for retry.
   - Retry daemon: polls `XPENDING`, checks delivery age, `XCLAIM` to retry queue, dead-letter after 5 attempts.

2. **Week 2 — Billing exactly-once + observability (2 engineers):**
   - Billing notifications carry `event_id` (UUID). Consumer checks `notifications_delivered` table (PostgreSQL) before processing. `INSERT ... ON CONFLICT DO NOTHING` enforces dedup.
   - Prometheus metrics on stream depth, consumer lag, retry counts, dead-letter queue size. Grafana dashboard.

3. **Ongoing — WebSocket push:**
   - Small consumer bridges notification streams into Redis Pub/Sub. WebSocket servers subscribe to the relevant channels. No new infrastructure.
