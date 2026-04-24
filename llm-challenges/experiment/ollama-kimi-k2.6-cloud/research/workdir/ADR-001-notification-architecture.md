# ADR-001: Notification Subsystem Architecture

**Status:** Proposed

**Date:** 2026-04-24

**Author:** Architecture Team

---

## Context

Our SaaS project-management platform (`85k MAU`, peak `~500 req/s`) currently sends email and webhook notifications synchronously inside the Flask HTTP request cycle. This has caused request timeouts (latency spikes to `8s`), silent failures with no retry mechanism, two cascading-failure incidents from slow webhook endpoints, and no delivery guarantees for billing-critical events.

We must decouple notification processing from the request cycle and build a system that supports:

- Async processing with retry and exponential backoff
- At-least-once delivery for general notifications
- Exactly-once semantics for billing events (trial expiry, payment failure)
- A foundation for real-time WebSocket push within two quarters
- 10× traffic headroom without re-architecting

**Team constraints:** 6 engineers (3 senior, 3 mid-level), zero dedicated infrastructure staff, modest budget (managed Confluent Cloud is unaffordable), and a hard requirement to deliver production value within two weeks of starting migration. We already operate Redis for sessions and rate-limiting. No one on the team has production Kafka experience.

---

## Decision

**We will use Redis Streams as the notification message bus.**

General notifications will be consumed via Redis Streams consumer groups, giving us at-least-once delivery with automatic claim and retry semantics (`XPENDING` / `XCLAIM`). For billing-critical events requiring exactly-once processing, consumers will perform idempotent de-duplication: each billing message carries a deterministic UUID, and the consumer attempts an `INSERT INTO processed_notifications (message_id) VALUES (...) ON CONFLICT DO NOTHING` in PostgreSQL before performing any side effect. The database unique constraint guarantees exactly-once semantics at the application level.

We will run a **dedicated Redis 7+ instance** for streams, separate from our session-cache node, to avoid memory pressure and eviction conflicts, but under the same operational model we already understand (single-primary with AOF + RDB persistence).

---

## Consequences

### Positive

1. **Operational velocity within the 2-week window.** The team already runs, monitors, and backs up Redis. Adding a streams workload requires only configuration changes and client-code updates, not learning ZooKeeper/KRaft, partition rebalancing, or JVM tuning.
2. **Throughput is more than sufficient.** Redis Streams routinely handles `>100k messages/sec` on modest hardware. Even at 10× growth (`5k req/s` peak) with multiple event types per request, we remain two orders of magnitude below Redis’s ceiling.
3. **Ordering guarantees per stream.** Redis Streams is an append-only log; within a single stream, messages are strictly ordered by ID. We will shard by notification type (`stream:emails`, `stream:webhooks`, `stream:billing`) so ordering is preserved per domain where it matters.
4. **Natural path to WebSocket push.** Redis pub/sub (or blocking `XREAD` on lightweight consumers) integrates cleanly with our planned real-time layer. Using the same data store reduces architectural sprawl.
5. **Cost.** A dedicated `cache.r6g.large` ElastiCache node (or equivalent self-managed instance) costs a fraction of any self-hosted Kafka cluster (3+ brokers) and is free of the licensing/subscription burden of managed Kafka.
6. **Consumer-group mechanics are built-in.** `XGROUP CREATE`, `XREADGROUP`, and automatic pending-entry-list management give us the consumer-group model we need without additional middleware.

### Negative / Mitigations

1. **Message retention is memory-bound, not disk-bound.** Kafka retains messages on disk for days or weeks cheaply; Redis Streams keeps data in memory. We will mitigate with `MAXLEN` / `XTRIM` policies (retaining the last `~500k` messages per stream, ~7 days at current volume) and archiving billing events to PostgreSQL after processing.
2. **Exactly-once is application-level, not broker-native.** Kafka’s idempotent producer + transactions provide a tighter exactly-once abstraction. Our PostgreSQL de-duplication table adds a database round-trip to every billing consumer loop. We accept this because billing events are low-volume compared to general notifications.
3. **Fewer stream-processing ecosystem tools.** Kafka has Kafka Connect, ksqlDB, and a mature monitoring ecosystem (e.g., Kafka Lag Exporter). For Redis Streams we will instrument consumer lag ourselves via `XLEN` and `XPENDING` metrics emitted to our existing Prometheus/Grafana stack.
4. **No cross-stream transactions.** If we later need atomic "publish to stream A and stream B," we will implement Saga-style compensation in application code rather than relying on broker transactions.
5. **Clustering/sharding story is simpler but less automated.** If we outgrow a single Redis node, we can shard by notification category across Redis Cluster slots, but re-sharding requires manual planning. Given our 10× headroom, we do not expect to hit this within the planning horizon.

---

## Alternatives Considered

### Apache Kafka

**Why it was rejected:**

Kafka is architecturally superior for massive-scale, long-retention stream processing. Its native exactly-once semantics (idempotent producers, transactions, consumer isolation levels) would remove the need for our application-level de-duplication table, and its disk-based retention model is more cost-effective for multi-day replay.

However, **self-hosted Kafka is operationally dangerous for a team with no Kafka experience and no infrastructure engineer.** A minimal production cluster requires 3 brokers, careful partitioning strategy, ISR management, consumer-rebalance tuning, and JVM memory/ GC monitoring. The learning curve alone violates our 2-week value-delivery constraint. A managed offering (Confluent Cloud, MSK) was explicitly ruled out by budget. Given our throughput (`500 req/s` today, `5k` at 10×), Kafka’s scale advantages are irrelevant; we would be paying massive operational tax for headroom we cannot use.

Therefore, we record that Kafka is the preferred technology *only if* the team later hires dedicated platform engineering or moves to a managed service budget. Under current constraints, it is the wrong trade-off.

---

## Related Decisions

- Billing consumers **must** validate message IDempotency against PostgreSQL before emitting side effects.
- All stream consumers **must** expose a health-check endpoint that fails when consumer lag (measured via `XPENDING` count) exceeds a tunable threshold.
- A follow-up ADR will be written before implementing WebSocket push to decide between Redis Pub/Sub and SSE.
