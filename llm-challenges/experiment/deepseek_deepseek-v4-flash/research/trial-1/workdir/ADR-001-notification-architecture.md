# ADR-001: Notification Subsystem — Async Decoupling with Redis Streams

**Status:** Proposed  
**Date:** 2026-05-22  
**Author:** Engineering team  
**Deciders:** Platform engineering (6-person team)

---

## Context

The notifications module (email + webhooks on task create/update/assign) runs synchronously inside the Flask HTTP request cycle. At current load (~500 req/s peak, 85k MAU, 2M tasks/month), this causes three interrelated failures:

1. **Request timeouts** — average 800ms, spikes to 8s when email/webhook providers lag.
2. **Silent drops** — a downed provider means the notification is lost with no retry or dead-letter path.
3. **Cascading failures** — slow webhook endpoints have twice caused PostgreSQL connection pool exhaustion, taking down unrelated features.
4. **No delivery guarantees** — billing-critical notifications (trial expiry, payment failure) have no exactly-once or at-least-once assurance.

### Scaling target

- Decouple notifications from the HTTP request cycle.
- Support retry with exponential backoff.
- At-least-once delivery for general notifications; exactly-once for billing events.
- Add WebSocket push within two quarters.
- Handle 10x traffic growth (~5k req/s peak) without re-architecting.

### Constraints

- Engineering team: 6 people (3 senior, 3 mid-level). No dedicated infrastructure engineer.
- **Redis is already in production** (session storage, rate limiting) — existing operational familiarity.
- **Zero Kafka experience** on the team today.
- Setup and migration must deliver value within **two weeks**.
- Budget is modest — managed Confluent Cloud is out of reach at full scale.

---

## Decision

**Use Redis Streams as the notification backbone.**

Every notification event is published to a Redis stream. A pool of async consumer workers (running as a separate service or sidecar) reads from the stream via consumer groups, dispatches the email/webhook/WebSocket push, acknowledges on success, and retries on failure with exponential backoff. Failed events exceeding the retry threshold land in a dead-letter stream for manual inspection.

---

## Consequences

### Advantages

| Property | How Redis Streams delivers it |
|---|---|
| **Async decoupling** | HTTP request writes to stream and returns immediately (<5ms). Consumers process independently. |
| **At-least-once delivery** | Consumer groups + PEL (Pending Entries List). Consumers must explicitly `XACK`. Crashed consumers are detected via `XPENDING`/`XAUTOCLAIM` and re-delivered. |
| **Retry with backoff** | Dead-letter pattern: consumer reads, dispatches, fails, re-queues with a visibility timeout. After N attempts, moves to a separate dead-letter stream via `XADD`. |
| **Exactly-once for billing** | Achieved at the consumer layer: idempotent processing (store `event_id` in PostgreSQL with a unique constraint, skip duplicates). Redis streams guarantee **at-most-once delivery per consumer** (once `XACK`'d); the consumer enforcement closes the gap to exactly-once. |
| **Throughput headroom** | Redis handles 100k–1M operations/second on modest hardware. At 500 req/s today (~5k req/s at 10x), we use <5% of capacity. No bottleneck. |
| **Ordering within partition** | A single stream preserves insertion order. For per-resource ordering (e.g., task-scoped events), use a stream per resource or a consistent shard key. |
| **WebSocket push** | Consumer reads from stream, pushes to connected WebSocket clients. Redis Pub/Sub alongside streams works naturally for real-time broadcast without additional infrastructure. |
| **Operational simplicity** | Team already runs Redis. No new daemon, no new state machine to learn, no additional monitoring surface. Redis Streams uses the same `redis-py` library the team knows. |
| **Setup velocity** | Production-ready prototype in days, not weeks. Enable within the 2-week constraint. |

### Disadvantages

| Limitation | Risk & Mitigation |
|---|---|
| **Message retention** | Redis is memory-bound. Streams trim by count or time (`XTRIM MAXLEN ~100k`). Long-term event history is the database's job (PostgreSQL). **Mitigation**: Archive processed events to PostgreSQL for audit; keep only unprocessed + recent messages in Redis. |
| **No built-in rebalancing for large fan-out** | Redis Streams consumer groups handle N consumers on 1 stream. For high fan-out (e.g., 10k consumers on one stream), Kafka outshines Redis. **Mitigation**: At our scale (tens of consumers), Redis is fine. If fan-out grows, we use one stream per subscriber type. |
| **Exactly-once is consumer-enforced, not native** | Kafka's transactions and idempotent producer reduce the burden on the consumer. Redis leaves idempotency entirely to the consumer. **Mitigation**: A unique constraint on `(event_id, notification_type)` in PostgreSQL is simple, well-understood, and sufficient for our billing volume (<1k events/day). |
| **Memory-bound at extreme scale** | At 100x+ growth beyond our target, memory costs for long streams become significant vs Kafka's disk-backed log. **Mitigation**: By that point the team will be larger and Kafka migration will be justified. This ADR is revisited at 50k req/s. |
| **No log compaction** | Kafka can compact by key (retain latest state per entity). Redis Streams cannot. **Mitigation**: We don't need compaction — notifications are immutable events, not state snapshots. Audit trail lives in PostgreSQL. |

---

## Alternatives Considered

### Apache Kafka (Rejected)

Kafka is the industry standard for event streaming and excels at properties we value: durable log, ordered partitions, consumer groups, exactly-once semantics via transactions. However, it is the wrong choice for this team, at this time, for this problem.

| Requirement | Why Kafka fails it |
|---|---|
| **Team size & expertise** | 6 people, zero Kafka experience. Kafka's operational surface — broker tuning, partition rebalancing, consumer lag monitoring, KRaft/ZooKeeper management — demands dedicated infrastructure attention. A 6-person team cannot absorb this without sacrificing product velocity. |
| **Setup timeline (≤2 weeks)** | Standing up a production Kafka cluster, tuning it for reliability, and integrating it into a Flask monolith in 2 weeks is unrealistic for a Kafka-naive team. Redis Streams achieves the same at the application level in 2–3 days. |
| **Budget** | Self-hosted Kafka on EC2 is operationally expensive (multiple brokers, storage, monitoring). Managed Confluent Cloud at our scale would exceed the modest budget. |
| **Proportionality** | Kafka is designed for millions of messages per second across thousands of partitions. Our peak is 500 req/s today, ~5k req/s at 10x. Redis Streams handles this with <5% CPU/memory headroom. Deploying Kafka for this throughput is like mooring a container ship to cross a pond. |
| **Exactly-once delta** | Kafka's exactly-once semantics (transactions, idempotent producer, EOS) remove some consumer burden but still require idempotent downstream writes for true end-to-end exactly-once. The gap between Kafka EOS and consumer-enforced idempotency (our Redis approach) is small at our volume. |

**When we would revisit Kafka:** If traffic exceeds 50k req/s, if we need to store multi-year event histories in-stream, or if we adopt an event-sourcing pattern that benefits from log compaction. At that point the team would also be larger, and a dedicated migration would be warranted.

---

## Summary

Redis Streams is the correct decision for this team, this scale, and this budget. It solves every stated problem — decoupled async processing, retry with backoff, at-least-once delivery, exactly-once for billing (via consumer idempotency), and a clear path to WebSocket push — without adding infrastructure the team cannot operate. Kafka provides marginal technical advantages that are irrelevant at our throughput level and impose operational costs the team cannot carry.

**Chosen: Redis Streams.**
