# ADR-001: Notification Subsystem — Async Processing with Redis Streams

**Status:** Proposed

---

## Context

The Notifier subsystem in our SaaS project management platform sends email and webhook notifications when tasks are created, updated, assigned, or completed. Currently, notifications are sent synchronously within the HTTP request cycle. This design has produced four systemic failures:

1. **Request timeouts** — Average response latency of 800ms spikes to 8s during peak hours as notification delivery blocks the HTTP response.
2. **Silent failures** — Email provider or webhook endpoint outages cause notifications to be dropped with no retry, no dead-letter queue, and no operator alert.
3. **Cascading failures** — Slow webhook endpoints exhaust database connection pools, taking down unrelated features (two production incidents this year).
4. **No delivery guarantees** — Billing-critical notifications (trial expiry, payment failures) have no at-least-once or exactly-once guarantee.

We must decouple notification delivery from the request cycle and introduce a message broker. The key constraints shaping this decision:

| Constraint | Detail |
|---|---|
| Team size | 6 engineers (3 senior, 3 mid), no dedicated infra engineer |
| Existing infra | Redis already in production for session storage and rate limiting |
| Kafka expertise | Zero — no team member has operated Kafka in production |
| Delivery timeline | Must deliver working async notifications within 2 weeks |
| Budget | Modest — cannot run managed Confluent Cloud at full scale |
| Current peak load | ~500 req/s during business hours |
| Scaling target | 10x traffic growth without re-architecting |
| Critical requirement | Exactly-once semantics for billing notifications |

Two options were evaluated: **Apache Kafka** and **Redis Streams**.

---

## Decision

**Use Redis Streams** for the notification subsystem.

### Justification

The decision is driven by the **operational envelope** the team can sustain, not by theoretical peak throughput. Redis Streams wins on every constraint that carries risk for this team:

**1. Zero new infrastructure.** Redis is already deployed, monitored, backed up, and understood by the team. Adding Kafka means provisioning brokers, tuning JVM heap, managing ZooKeeper or KRaft quorum, and learning a new operational vocabulary (ISR, leader election, partition reassignment, min.insync.replicas). For a team of six with no dedicated infra engineer, this alone is the decisive factor.

**2. 2-week delivery is feasible with Redis Streams.** The existing Redis client library already supports stream operations (`XADD`, `XREADGROUP`, `XACK`, `XAUTOCLAIM`). A minimal working system — push notification payloads into a stream, have a background worker consume and deliver — can be prototyped in days and shipped in under two weeks. Kafka would require provisioning infrastructure, learning the client API, and debugging connection/auth issues before writing a single business-logic consumer.

**3. Redis Streams handles the required throughput comfortably.** Current peak is ~500 req/s, and the 10x growth target is ~5,000 req/s. A single Redis instance handles 100k+ ops/s for simple operations — stream writes are marginally more expensive but still well within budget. At ~5k notifications/s, Redis is operating at ~5% of capacity, leaving headroom for the session and rate-limiting workloads it already serves.

**4. Exactly-once billing semantics: achieved via consumer-side idempotency.** Redis Streams offers at-least-once delivery natively (consumer groups with PEL tracking). To reach exactly-once, the pattern is:

- Producer assigns a deterministic, semantically unique message ID (e.g., `billing:trial-expired:user-8421:invoice-399`).
- Consumer checks a deduplication store (Redis Set or a database unique constraint) before processing. If already processed, issue `XACK` and skip.
- This follows the same pattern Kafka's exactly-once implementation ultimately requires — downstream idempotency — because transactional outboxes and idempotent writers still cannot prevent duplicate delivery across broker failures.

**5. Future WebSocket push integration is natural.** The notification consumer can fan out to a Redis Pub/Sub channel that WebSocket servers subscribe to — a well-established pattern. No additional infrastructure required.

**6. Kafka's advantages are real but premature.** Kafka excels at high-throughput, long-retention event sourcing across many consumers with independent offset management. Our use case is a single logical consumer (the notification worker) that processes short-lived messages (retries expire after hours, not days). Kafka's partitioning and replay capabilities add complexity with no near-term benefit.

---

## Consequences

### Positive

- **Immediate operational continuity** — Same Redis cluster, same monitoring dashboards, same backup/restore procedures. No new alerting rules or runbooks to write.
- **Fast time-to-value** — A working async notification pipeline can ship within 1–2 weeks.
- **Low cognitive load** — The team knows Redis key expiration, memory management, and failover behaviour. No JVM tuning, no broker configuration, no partition strategy to debate.
- **Adequate throughput margin** — ~5k messages/s at 10x growth leaves 95% headroom on a single Redis instance.
- **Natural fit for consumer-group retry** — `XAUTOCLAIM` and `XPENDING` provide built-in visibility into stuck messages; a scheduled job can move messages to a dead-letter stream after N retries.
- **WebSocket push is additive** — Adding real-time notifications uses the same stream consumer plus a Pub/Sub fan-out, no new infrastructure.

### Negative

- **Memory-bound retention** — Redis Streams live in RAM. If consumers fall behind far enough to exhaust memory, messages are evicted (if `maxmemory-policy` evicts) or writes fail. This requires monitoring consumer lag and setting conservative `MAXLEN` (~100k entries ≈ ~100MB for typical notification payloads). Kafka writes to disk and can retain terabytes.
- **No built-in partition rebalancing** — Redis consumer groups assign messages round-robin across consumers. If a consumer crashes, `XAUTOCLAIM` redelivers its pending messages, but there is no automatic rebalancing of partition ownership as in Kafka. At our worker count (2–4 consumers), this is manageable but requires manual scaling of consumer instances.
- **No native exactly-once at the broker level** — The deduplication logic must be implemented in the consumer. This is well-understood but adds a small implementation and testing cost.
- **Limited replay capability** — To replay old messages (e.g., re-send all failed notifications after an outage), you must either keep the stream long enough or log to a separate durable store. Kafka's log compaction makes this trivial.
- **Ecosystem maturity** — Kafka has a richer ecosystem of connectors, stream processors (Kafka Streams, ksqlDB), and observability tooling. Redis Streams has `redis-cli` and third-party tools — sufficient for our scale, but less polished.
- **Future migration risk** — If the notification subsystem eventually needs to support event sourcing, audit logging with multi-year retention, or hundreds of independent consumer groups, a migration to Kafka would be warranted. The current ADR does not preclude that — it defers it until the scaling and complexity needs clearly exceed Redis Streams' capabilities.

---

## Alternatives Considered

### Apache Kafka — Rejected

Kafka is architecturally superior on paper:

- **Exactly-once semantics** at the broker level via idempotent producers + transactions.
- **Disk-based persistence** with configurable retention (time or size), enabling replay and audit.
- **Automatic partition rebalancing** when consumers join or leave a group.
- **Higher throughput** (millions of messages/s) — far beyond our needs but never a bottleneck.
- **Ecosystem** — Kafka Connect, Kafka Streams, and extensive monitoring tooling.

**Why it was rejected despite these strengths:**

1. **Operational risk is too high for this team.** A self-hosted Kafka cluster requires at least 3 brokers for a quorum, careful JVM heap tuning, network configuration, partition count decisions, and ongoing broker maintenance. With zero Kafka experience and no dedicated infra engineer, every operational incident becomes a learning experience paid in downtime. Managed Kafka (Confluent Cloud, Amazon MSK) mitigates this but violates the budget constraint at full scale — MSK costs ~$500–1,500/month for a modest 3-broker cluster, and Confluent Cloud is more.

2. **2-week delivery timeline is unrealistic.** Learning the Kafka client API, provisioning the cluster, configuring authentication/authorization, tuning producer/consumer settings, and debugging the first deployment would consume the entire window with no working system delivered.

3. **Kafka is overengineered for current and near-term scale.** At 500 req/s (5,000 at 10x), Redis Streams handles the load with 95% headroom. Kafka's partitioning model solves problems we don't have — multiple consumer groups with independent offsets, long-term log compaction, and throughput in the millions.

4. **Kafka does not eliminate the consumer-side deduplication requirement.** Kafka's exactly-once semantics guarantee that a message is written to the log exactly once. But if the consumer processes the message and crashes before committing the offset, the message will be redelivered on rebalance. Consumer-side idempotency is still required for true end-to-end exactly-once — the same work Redis Streams demands. So Kafka's transactional API removes one class of duplicates but not all.

**Rejection summary:** Kafka's architectural advantages cannot be realized within the team's operational capacity, timeline, or budget. Redis Streams meets all requirements with a fraction of the risk.

---

*Authored by Engineering. Approved pending team review.*
