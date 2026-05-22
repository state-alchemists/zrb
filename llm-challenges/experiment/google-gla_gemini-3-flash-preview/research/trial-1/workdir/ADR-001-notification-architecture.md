# ADR-001: Notification Subsystem Architecture

**Status:** Proposed

---

## Context

The Notifier subsystem in our SaaS project management platform handles email and webhook notifications when tasks are updated, assigned, or completed. At 85K MAU and ~2M tasks/month (peak 500 req/s), the current approach — sending notifications synchronously inside the HTTP request cycle — has created four interrelated failures:

1. **Request timeouts** — average notification latency is 800 ms, spiking to 8 s at peak, blocking the HTTP response.
2. **Silent failures** — a dead email provider or webhook endpoint drops the notification with no retry or dead-letter queue.
3. **Cascading failures** — two incidents this year where a single slow webhook triggered connection-pool exhaustion that took down unrelated features.
4. **No delivery guarantees** — billing-critical events (trial expiry, payment failure) must achieve at-least-once delivery and exactly-once where feasible, but the current system has zero guarantees.

The target architecture must:
- Decouple notification dispatch from the HTTP request cycle.
- Support retry with exponential backoff.
- Guarantee at-least-once delivery for billing events, exactly-once where feasible.
- Lay a foundation for real-time WebSocket push within two quarters.
- Handle 10× traffic growth without re-architecting.

**Constraints:**
- Engineering team of 6 (3 senior, 3 mid-level), no dedicated infrastructure engineer.
- Redis is already in production for session storage and rate limiting.
- Zero Kafka experience on the team.
- Must deliver value within two weeks of setup/migration work.
- Budget does not cover managed Confluent Cloud at full scale.
- Exactly-once semantics are required for billing notifications.

---

## Decision

**Adopt Redis Streams** as the notification message broker. We will:
- Publish notification events to Redis Streams from the HTTP handler (non-blocking, ~sub-millisecond write).
- Run consumer workers in separate processes (or threads) that read from the stream via consumer groups.
- Use `XPENDING` / `XCLAIM` for retry with exponential backoff and a dead-letter stream for exhausted retries.
- Implement idempotent consumers keyed on a notification ID to achieve exactly-once semantics for billing events.

This can be deployed incrementally in under one week: add stream writes to the notification service, then ship consumer workers in the same deploy cycle. No new infrastructure, no new credential management, no new latency-sensitive dependency to monitor.

---

## Consequences

### ✅ Pros

| Property | Redis Streams |
|---|---|
| **Operational complexity** | Zero new infrastructure. Redis is already deployed, monitored, and backed up. The team knows its failure modes, memory profiles, and operational knobs. |
| **Time to value** | 3–5 days to first fully asynchronous notification delivery. The existing `redis-py` client has first-class Streams support. |
| **Throughput at current scale** | Redis handles ~100K msg/s on modest EC2 instances. At 500 req/s (5K at 10×), we are at 5% of capacity — ample headroom. |
| **Consumer groups** | First-class support via `XGROUP`, `XREADGROUP`, and `XACK`. Automatic consumer-group tracking with `XPENDING` for unobtrusive audit. |
| **Retry and dead-letter** | `XPENDING` + `XCLAIM` provide retry tracking out of the box. A scheduled job can move expired messages to a dead-letter stream. |
| **Exactly-once feasible** | Using notification IDs as idempotency keys, consumers deduplicate on the database side. This achieves exactly-once semantics without relying on broker-level guarantees. |
| **Budget** | Already paid for. No new AWS services, no Confluent Cloud tier. |
| **WebSocket foundation** | Redis Pub/Sub (or a second stream) can bridge to a WebSocket server with zero additional broker infrastructure. |
| **Team alignment** | Redis is already in the team's collective mental model. No new protocol, no JVM, no ZooKeeper. |

### ❌ Cons

| Property | Redis Streams |
|---|---|
| **Memory-bound retention** | Streams live in RAM (with optional RDB/AOF persistence). Long retention (days+) consumes real memory. We will set a moderate retention period (e.g., `MAXLEN ~ 100K`) and rely on database-side records for long-term audit. |
| **No built-in partition scaling** | A single Redis stream lives on one shard. If we outgrow single-node throughput, we must shard across Redis Cluster or use separate streams per partition key (e.g., per tenant). This is explicit application logic rather than automatic Kafka partition rebalancing. |
| **No built-in stream processing** | No Kafka Streams, KSQL, or Connect ecosystem. Complex processing pipelines (e.g., fan-out to email + webhook + WebSocket with different retry policies) must be implemented in application code. |
| **Manual consumer rebalancing** | If a consumer dies, other consumers in the group do not automatically rebalance — we must use `XCLAIM` with a visibility timeout. This is well-documented but more DIY than Kafka's rebalance protocol. |
| **Exactly-once is consumer-managed** | The broker provides at-most-once or at-least-once delivery. Achieving exactly-once requires idempotent consumers — which we already need for billing regardless of broker, but it's not a broker-level guarantee. |

---

## Alternatives Considered

### Apache Kafka

**Why it was seriously considered:** Kafka is the industry standard for asynchronous event pipelines. It provides:

- **Higher throughput** — millions of messages per second with proper tuning.
- **Strong partition ordering** — all messages within a partition are strictly ordered, and the consumer offset model makes replay deterministic.
- **Long retention** — disk-based storage allows days or weeks of retention with no memory pressure.
- **Exactly-once semantics** — idempotent producers and Kafka transactions provide broker-guaranteed exactly-once for produce and consume (EOS).
- **Consumer-group rebalancing** — fully automatic when consumers join or leave.
- **Ecosystem** — Kafka Connect, Kafka Streams, KSQL, schema registry, and a deep library of integrations.

**Why it was rejected:**

1. **Operational overhead is prohibitive for a 6-person team.** Self-hosting Kafka means managing broker JVM heap, ZooKeeper or KRaft quorum, partition reassignment, topic replication, controller elections, and a dedicated monitoring stack (JMX exporter, Burrow, Cruise Control). Every one of these is a documented failure vector. The team has no operational experience with any of them.

2. **No Kafka expertise on the team.** Introducing Kafka means a long learning curve before the team can confidently operate it in production. The three mid-level engineers would need weeks of ramp-up before contributing meaningfully to the notification pipeline. Redis Streams leverages the team's existing Redis knowledge.

3. **Overkill for current scale.** Kafka shines at very high throughput (millions of messages per second) and complex stream processing. At 500 req/s, it is a sledgehammer for a finishing nail. We would absorb Kafka's complexity while using only a tiny fraction of its capability.

4. **Budget constraints.** Managed Kafka (Confluent Cloud) at the scale needed for production SLA is expensive. Self-hosted Kafka has a hidden cost in engineering hours for setup, tuning, and incident response — a cost the ~$150/month Redis instance already covers.

5. **Time to value exceeds the constraint.** Standing up a production Kafka cluster with replication, monitoring, and backup would take 2–4 weeks minimum, even with experience. The two-week window means we would ship *nothing* for the first sprint, whereas Redis Streams delivers value within the first week.

---

## Recommendation

**Use Redis Streams.** It satisfies every stated requirement, respects every constraint, and delivers production value within the first sprint. The only genuine long-term risk — single-shard throughput — does not bind at our current scale or at the 10× target (5K req/s). If we ever grow beyond that, migrating to Kafka at that point will be a focused, justified re-architecture with concrete traffic data and a larger team to operate it. Redis Streams buys us years of headroom and zero operational debt today.
