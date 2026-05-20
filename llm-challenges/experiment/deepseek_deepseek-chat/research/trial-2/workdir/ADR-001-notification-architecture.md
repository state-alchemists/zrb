# ADR-001: Notification Architecture — Redis Streams

**Status:** Proposed

---

## Context

The notifications module in our SaaS project management platform currently runs synchronously inside the Flask HTTP request cycle. As we've grown to 85,000 MAU and ~2M tasks/month, this has caused three classes of production incidents: request timeouts averaging 800ms with spikes to 8s, silent notification drops with no retry path, and cascading failures from slow webhook endpoints exhausting the connection pool.

We need to decouple notification delivery from the request cycle and introduce an async event-driven architecture. The system must support at-least-once delivery for general notifications, exactly-once semantics for billing-critical events (trial expired, payment failed), retry with exponential backoff, and a path to real-time WebSocket push within two quarters. The solution must handle 10x traffic growth (5000 req/s peak) without re-architecting.

The team is six engineers (three senior, three mid-level) with no dedicated infrastructure engineer. We already run Redis in production for session storage and rate limiting. Nobody on the team has Kafka experience. The budget is modest — managed Confluent Cloud is not feasible at full scale. The migration must deliver value within two weeks.

---

## Decision

**Use Redis Streams as the notification event bus.**

We will replace the inline notification calls in the Flask request cycle with writes to a Redis Stream. A set of background worker processes (one per notification channel: email, webhook, WebSocket) will consume from dedicated consumer groups on the stream. The existing Redis instance is sufficient to start; we'll provision a second, dedicated Redis instance sized for the notification workload before going to production.

### Architecture Sketch

```
HTTP Request → Flask handler → XADD to Redis Stream → return 200 OK
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
              Email Worker  Webhook Worker  WS Worker (Q2)
              (consumer     (consumer       (consumer
               group A)      group B)        group C)
```

Each worker operates independently with its own consumer group, so a slow webhook endpoint no longer blocks email delivery or the HTTP response.

### Exactly-Once for Billing Events

Billing notifications carry a unique event ID generated at write time (`XADD`). The email worker acknowledges consumption via `XACK` only after the downstream provider confirms delivery. On restart or failure, `XPENDING` reclaims unacknowledged messages. The worker is idempotent — duplicate deliveries are detected by the event ID and silently dropped before the provider call. This gives us exactly-once delivery without requiring Kafka's transaction coordinator.

### Retry with Exponential Backoff

Messages that fail delivery are not `XACK`'d. A retry supervisor process runs `XPENDING` on a scheduled interval, uses `XCLAIM` to transfer ownership of stalled messages, and re-enqueues them into a retry stream with a `retry_count` field. After N failures, the message moves to a dead-letter stream for manual inspection.

### WebSocket Push Path

Redis Streams natively supports blocking reads (`XREADGROUP BLOCK`). In Q2, we'll add a WebSocket worker that consumes the same stream and pushes events to connected clients via a shared Redis pub/sub channel. No infrastructure change required.

---

## Consequences

### Pros

- **Zero new infrastructure.** Redis is already in production. A dedicated notification Redis instance is a single `elasticache` provisioning call — no new operational surface.
- **Team familiarity ships fast.** Every engineer already understands Redis data structures and operational patterns. The learning curve is hours, not weeks. The core migration (XADD in request handler + consumer group workers) can be built and deployed within the two-week constraint.
- **Adequate throughput.** At 500 req/s today, 5000 req/s at 10x growth, Redis Streams handles this comfortably. A single Redis instance can sustain 100k+ operations/second on modest hardware — well above our projected peak.
- **Consumer groups for ordered parallel processing.** Each notification channel gets its own consumer group with independent offset tracking. Failed consumers don't block other channels. Within a consumer group, messages are distributed across workers with at-least-once guarantees via the PEL (Pending Entry List).
- **Exactly-once for billing.** Idempotent consumer + unique event ID + XACK-on-confirm gives exactly-once semantics without the complexity of Kafka transactions. Proven pattern documented in Redis Streams literature.
- **Natural WebSocket path.** Redis Streams' blocking read model maps directly to a push-based WebSocket subscriber. No additional message broker needed.
- **Operational simplicity for a small team.** No ZooKeeper/KRaft clusters to manage, no partition rebalancing to tune, no replication factor decisions. Redis failover is handled by ElastiCache or a simple sentinel setup — both patterns already in use.

### Cons

- **Memory-bound storage.** Redis holds stream data in memory. At 5000 req/s with message retention for retry windows, memory costs scale with backlog. Mitigation: use `MAXLEN ~ 100000` to cap stream length, move long-term audit trails to PostgreSQL or S3, and size the Redis instance appropriately (~16GB covers weeks of backlog at our message sizes).
- **No native partitioning.** A single Redis stream node is the throughput ceiling. If we exceed ~100k msg/s or need geo-distribution, we'd need to shard across streams manually (e.g., by tenant ID or event type). This is a future problem — our projected 5000 req/s is well within a single node's capacity.
- **Weaker ordering guarantees than Kafka.** Redis Streams guarantees ordering within a shard (single stream), but does not offer Kafka's total ordering across partitions with a single partition key. Mitigation: for billing notifications, all billing events share a common stream key, maintaining strict order within that domain.
- **Consumer group rebalancing is manual.** Kafka automatically reassigns partitions when a consumer joins or leaves. Redis requires manual monitoring of `XPENDING` and `XCLAIM` to handle consumer failures. The retry supervisor pattern addresses this, but it's code we must write and maintain.
- **Message persistence is best-effort (AOF/backup).** Redis persistence (RDB snapshots, AOF logs) is not as battle-tested for message durability as Kafka's disk-backed commit log. In practice, with AOF fsync=always and daily RDB snapshots, we achieve acceptable durability for the notification use case. The true source of truth for billing events remains our PostgreSQL transaction log — the stream is a delivery channel, not a record of record.

---

## Alternatives Considered

### Apache Kafka — Rejected

Kafka is the industry standard for event streaming and excels at the problems we need to solve: durable message retention on disk, automatic consumer group rebalancing, built-in partitioning for horizontal scale, and Kafka's Exactly-Once Semantics (EOS) via the transaction coordinator and idempotent producers. It would handle 10x growth without breaking stride and would be the right answer for a larger, more operationally mature team.

However, several factors weigh against Kafka given our current constraints:

- **Team readiness gap.** Zero Kafka experience across six engineers. The learning curve spans producer/consumer API semantics, partition strategy, offset management, broker tuning, and failure recovery. A production-ready deployment is realistically 4-6 weeks for this team — exceeding our two-week constraint.
- **Operational tax.** Kafka requires at least three brokers for a resilient cluster, ZooKeeper or KRaft for consensus, monitoring for lag/under-replicated partitions, and careful OS tuning (page cache, disk I/O scheduler). For a team with no dedicated infrastructure engineer, this is a significant ongoing burden.
- **Budget limitation.** Managed Confluent Cloud at 5000-10000 msg/s with retention for retry windows costs ~$500-1500/month at our projected scale. Self-hosted Kafka carries EC2/RDS-like costs plus engineering time. The existing Redis instance is already paid for; a dedicated notification Redis adds ~$50-100/month.
- **Over-provisioned for current scale.** Kafka's partitioning model shines at 100k+ msg/s across dozens of partitions. At our projected 5000 req/s peak, Redis Streams provides equivalent delivery guarantees without the operational machinery. Kafka's strengths (disk-backed retention, multi-tenant partitioning, stream processing with Kafka Streams/kSQL) are not needed by a notification subsystem that is fundamentally a queue-and-dispatch pattern.
- **Two-week constraint is non-negotiable.** Standing up Kafka with operational readiness (monitoring, backup, consumer group management) in two weeks with a Kafka-naive team is not a realistic plan. Redis Streams can be in production in three days.

### PostgreSQL LISTEN/NOTIFY — Rejected (Briefly Considered)

PostgreSQL's `NOTIFY` command offers a pub/sub mechanism with zero new infrastructure. However, it lacks consumer groups, message persistence beyond `notify` channel capacity, retry semantics, and any delivery guarantee. It is suitable for cache invalidation signals, not durable notification delivery.

### SQS + SNS — Rejected (Briefly Considered)

AWS SQS and SNS eliminate operational overhead entirely. However, they tie us to AWS lock-in for the messaging layer, add per-message costs at scale (SQS costs ~$0.40/1M requests; at 5000 req/s that's ~$520/month in SQS alone), and their latency characteristics (SQS has a minimum polling latency of ~100ms with long polling) are higher than Redis Streams' sub-millisecond XADD latency. The existing Redis investment also makes this a more expensive option with no clear operational advantage.

---

## Recommendation

Adopt Redis Streams as the notification event bus. The decision is driven by the specific constraints of our team size, existing infrastructure, and delivery timeline. Redis Streams meets every stated requirement (async decoupling, retry with backoff, at-least-once delivery, exactly-once for billing via idempotent consumers, WebSocket path) while introducing zero new infrastructure and no new operational surface. The throughput headroom is sufficient for 10x growth. If our scale outpaces Redis Streams' single-node capacity in the future, we can migrate to Kafka then — with the added benefit of having a team that now deeply understands the event-driven patterns Kafka would serve.

**Timeline:** Core migration (XADD in request handlers + consumer group workers for email and webhook) in 1 week. Retry supervisor + dead-letter queue in week 2. Billing exactly-once in week 3 (extends the two-week window by one week, which is acceptable for the most critical path).

---

*Last updated: 2026-05-20*
