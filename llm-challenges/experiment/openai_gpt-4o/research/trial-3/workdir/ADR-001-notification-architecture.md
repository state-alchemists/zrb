# ADR-001: Notification Subsystem Architecture

**Status:** Proposed

---

## Context

The Notifier subsystem in our SaaS project management platform handles email and webhook delivery when tasks are updated, assigned, or completed. Currently, notifications are sent synchronously inside the HTTP request cycle, which has caused:

- **Request timeouts**: Average latency 800ms, spikes to 8s at peak (~500 req/s). Users wait for external email/webhook calls before getting a response.
- **Silent failures**: Failed email provider or webhook calls drop notifications permanently — no retry, no dead-letter queue.
- **Cascading failures**: Slow webhook endpoints have caused connection pool exhaustion twice this year, degrading unrelated features.
- **No delivery guarantees**: Billing-critical events ("trial expired", "payment failed") lack at-least-once or exactly-once guarantees.

We need to decouple notification dispatch from the HTTP cycle into an async processing pipeline that supports retry, delivery guarantees, and future real-time WebSocket push — while respecting our team's operational capacity.

### Constraints

| Constraint | Detail |
|---|---|
| Team | 6 engineers (3 senior, 3 mid), no dedicated infra engineer |
| Kafka experience | None on the team |
| Existing infrastructure | Redis already deployed (session storage, rate limiting) |
| Setup timeline | Must deliver value within 2 weeks |
| Budget | Modest — no managed Confluent Cloud at full scale |
| Growth target | 10x current load (~5,000 req/s peak) |
| Delivery requirement | Exactly-once for billing notifications |

---

## Decision

**Use Redis Streams** for the notification queue.

The existing Redis instance will serve as the broker, with notifications published as stream entries and consumed by one or more async worker processes (run via a separate Python process or a lightweight task runner). Failed messages are tracked via `XPENDING`, retried with exponential backoff, and moved to a dead-letter stream after exceeding the retry limit. Billing notifications use an idempotency key (derived from `event_id + notification_type`) stored in Redis itself, enabling exactly-once semantics at the application level.

### Architecture Sketch

```
HTTP Request
    │
    ▼
Flask handler ──XADD──▶ Redis Stream (notifications)
                            │
                            ▼
              Worker process ──XREADGROUP──▶ Stream entries
                            │
                    ┌───────┴───────┐
                    ▼               ▼
                Email API       Webhook call
                    │               │
                    └───────┬───────┘
                            ▼
                    XACK on success
                    XPENDING on failure → retry queue
                    Dead-letter after N retries
```

---

## Consequences

### 👍 Positive

1. **Zero new infrastructure.** Redis is already deployed and operated today. No new brokers, ZooKeeper clusters, or JVM runtimes to manage. The ops burden on a 6-person team stays flat.

2. **Fastest path to value.** A working async notification queue can be shipped in days using `redis-py`'s `StreamConsumer` — well within the 2-week constraint. No learning curve for JVM/ZooKeeper/KRaft.

3. **Adequate throughput.** Redis handles 100k+ ops/s on modest hardware. At 5,000 req/s peak (10x growth), the notification load is well under Redis's ceiling even with retries and acks factored in. Throughput is not a binding constraint at this scale.

4. **Consumer groups with ordering.** Redis Streams consumer groups (`XREADGROUP`) partition messages across workers while maintaining ordering within a single stream entry. For notification-level ordering (vs. per-key ordering), this is sufficient.

5. **Retry and dead-letter out of the box.** `XPENDING` lists unacknowledged messages. `XCLAIM` transfers ownership of stalled messages to another consumer. A dedicated dead-letter stream can be populated after `MAXLEN` retries — no custom queue management needed.

6. **Exactly-once for billing via idempotency.** Since Redis is already the data store, billing notifications carry a unique idempotency key (`{billing_event_id}:{notification_type}`) that the consumer checks via `SET NX` before dispatching. If the key exists, the notification is a no-op. This gives exactly-once semantics at the application level regardless of stream delivery semantics.

7. **Simpler path to WebSocket push.** The same Redis instance can use `PUBLISH`/`SUBSCRIBE` in parallel to push real-time notifications to WebSocket servers, keeping the codebase on a single technology. Kafka would require a separate connector layer.

### 👎 Negative

1. **Memory-bound retention.** Redis stores streams in RAM. At 10x load with retries and dead-letter backlog, memory usage grows. We must set `MAXLEN` (~10k entries, ~100MB at typical notification size) and archive completed events to PostgreSQL or S3 daily. Kafka writes to disk and retains indefinitely.

2. **No built-in log compaction.** Kafka can compact by key, retaining only the latest message per key (useful for "latest state" rebuilds). Redis Streams does not support this. For our use case (notification queue, not event-sourced state machine), this is not a meaningful loss.

3. **No stream processing ecosystem.** Kafka has KSQL, Kafka Connect, and a rich connector ecosystem. Redis Streams relies on custom consumer code. Given we need a notification queue, not a stream processing pipeline, this simplicity is actually an advantage for a 6-person team.

4. **Exactly-once is application-level, not broker-level.** Redis Streams provides at-least-once delivery. Exactly-once requires the idempotency-key pattern described above. Kafka Transactions can provide exactly-once at the broker level but introduce significant complexity (transaction coordinators, commit protocols) — and still require application-level idempotency in practice for exactly-once *output* to external systems (email, webhooks).

5. **Future scaling ceiling.** Redis Streams does not natively partition across multiple Redis nodes. If we outgrow a single Redis instance (unlikely at 10x, but possible at 100x+), we would need to shard streams manually or migrate to Kafka at that point. The ADR should be revisited if traffic exceeds ~50,000 req/s.

---

## Alternatives Considered

### Apache Kafka (Rejected)

**Why it was seriously considered:** Kafka is the industry standard for async event pipelines. It offers higher raw throughput (millions of msg/s), disk-based persistence with configurable retention, log compaction, exactly-once via transactions, and a mature consumer-group model. For a team planning to add stream processing, event sourcing, or an event-driven architecture, Kafka is a natural fit.

**Why it was rejected:**

| Concern | Detail |
|---|---|
| **Operational complexity** | Kafka requires ZooKeeper (or KRaft in newer versions), multiple brokers, replication configuration, partition rebalancing, JMX monitoring, and ongoing tuning. A 6-person team with no Kafka experience and no dedicated infra engineer cannot operate Kafka reliably. The learning curve alone exceeds our 2-week timeline. |
| **Infrastructure cost** | A production Kafka cluster needs at least 3 brokers for fault tolerance, plus ZooKeeper nodes. On AWS, this starts at ~$500–1,000/month for modest instances. Managed Confluent Cloud is explicitly out of budget. MSK reduces ops but adds ~$300–600/month before storage. Redis Streams reuses existing infrastructure at zero marginal cost. |
| **Overkill for current scale** | Kafka shines at millions of messages per second across hundreds of partitions. At 500 req/s (5,000 at 10x), we would use < 1% of Kafka's capacity while paying 100% of its complexity. Redis handles this load trivially. |
| **Setup timeline violation** | Deploying Kafka: provisioning brokers, configuring ZooKeeper/KRaft, setting up monitoring, tuning JVM heap, writing a producer client, writing a consumer client, implementing retry/dead-letter from scratch (no XPENDING equivalent). This cannot be done within 2 weeks by a Kafka-naive team. Redis Streams is already available. |
| **Exactly-once is still application-level for our use case** | Kafka Transactions provide exactly-once semantics within the Kafka ecosystem (produce → process → commit), but we are sending *external* side effects (email, webhook). Exactly-once delivery to an external API still requires idempotency keys at the application layer — with or without Kafka Transactions. The transactional overhead (isolation level, commit protocol, zombie fencing) adds complexity with zero benefit for our external-output use case. |
| **No existing investment** | We already run Redis. Switching to Kafka means operating a second data infrastructure system (Redis for cache + Kafka for queues) instead of leveraging the one we already have. |

### Thread Pool / Celery with PostgreSQL (Rejected early)

Using Celery with PostgreSQL (`django-celery-results` or RabbitMQ) was briefly considered. Rejected because: PostgreSQL-based queues add load to our already constrained primary database; Celery adds a broker dependency (RabbitMQ or Redis — which circles back to Redis); and the operational surface area (beat scheduler, multiple queue types, result backends) is broader than a pure Redis Streams approach.

---

## Recommendation

**Adopt Redis Streams.** It is the fastest, safest, and most cost-effective path to an async notification pipeline given the team size, existing infrastructure, timeline constraints, and current scale. Kafka is the right choice for a future where we need event sourcing, stream processing, or 100x+ our current load — but that future is not today and not within the 2-week delivery horizon.
