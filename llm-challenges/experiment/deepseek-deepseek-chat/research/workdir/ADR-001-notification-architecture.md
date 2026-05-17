# ADR-001: Notification Subsystem — Async Event Broker

**Status:** Proposed

---

## Context

The Notifier subsystem sends emails and webhooks when tasks are updated, assigned, or completed. Currently it runs synchronously inside the HTTP request cycle, causing request timeouts (800ms avg, 8s spikes), silent failures when providers are down, cascading connection-pool exhaustion, and no delivery guarantees for billing-critical events.

We must decouple notification delivery from HTTP requests. The chosen event broker must support:

- **Async dispatch** — producers enqueue, consumers deliver outside the HTTP cycle.
- **Retry with exponential backoff** — failed deliveries must be retried, not dropped.
- **At-least-once delivery** for billing events; exactly-once where feasible.
- **Consumer groups** — multiple workers sharing consumption of a stream.
- **Future WebSocket push** — the broker should accommodate real-time push within 2 quarters.
- **10x traffic growth** — current peak is ~500 req/s; we need headroom.

**Constraints:**

- Team: 6 engineers (3 senior, 3 mid-level), no dedicated infrastructure engineer.
- Redis is already in production (session storage, rate limiting).
- Zero Kafka experience on the team today.
- Setup/migration must deliver value within 2 weeks.
- Budget cannot support managed Confluent Cloud at full scale.
- Exactly-once semantics required for billing notifications.

---

## Decision

**Use Redis Streams as the notification event broker.**

Redis Streams is the better fit for our team size, existing infrastructure, and scaling targets. We will model each notification type (task_assigned, task_completed, billing_expired, etc.) as a Redis Stream, use consumer groups with `XREADGROUP` for at-least-once delivery, and implement exactly-once semantics for billing at the consumer level via idempotency keys stored in PostgreSQL.

---

## Rationale

### 1. Existing infrastructure leverage

We already run Redis for session storage and rate limiting. Adding Streams requires zero new servers, zero new credentials, zero new monitoring surface. The Redis Cluster already in place handles failover. A Kafka deployment would require provisioning and operating a ZooKeeper ensemble (or KRaft quorum), brokers, and a new monitoring stack — a significant operational burden for a 6-person team with no dedicated ops engineer.

### 2. Time to value

Redis Streams can be in production within days. The team knows the Python `redis` library. A background worker consuming streams via `XREADGROUP` is a pattern any mid-level engineer can implement and debug. Kafka's learning curve (partitions, offsets, consumer rebalancing, `kafka-consumer-groups` CLI) would delay the first working notification by weeks — well past the 2-week constraint.

### 3. Throughput is sufficient

At peak, the platform handles ~500 req/s. Not every request generates a notification — a generous upper bound is ~200 notification events/s at peak, or ~17M/day. Redis Streams sustains ~100K msg/s per stream instance. Even at 10x traffic (~2K events/s), Redis Streams has an order-of-magnitude headroom. Kafka's million-msg/s throughput is unnecessary here.

### 4. Consumer groups and ordering

Redis Streams provides **total ordering** within a single stream — all consumers in a group see messages in insertion order. This is simpler and more predictable than Kafka's per-partition ordering, where total-order requires a single partition (defeating horizontal scaling) or client-side merging. For notification sequencing (e.g., "task assigned" before "task completed"), total ordering is valuable.

### 5. Retry and dead-letter queues

Redis Streams' PEL (Pending Entries List) tracks unacknowledged messages per consumer. XPENDING reveals stuck messages; XCLAIM reassigns them to a healthy consumer. Dead letters are implemented by writing failed messages to a separate `notifications:dlq` stream on the final retry. This maps cleanly to the retry-with-exponential-backoff requirement.

### 6. Exactly-once for billing

Neither Redis Streams nor Kafka provides exactly-once semantics out of the box without consumer cooperation. Both require idempotent consumers. Our approach:
- Billing notifications carry a unique `idempotency_key` (UUID).
- The consumer checks a unique constraint in PostgreSQL before sending.
- This works regardless of the broker choice and is the industry-standard pattern.
- Redis Streams' lack of native exactly-once producer semantics is not a blocker because billing events are enqueued by our own application code, which can enforce idempotency at the producer level (deduplicate before XADD).

### 7. WebSocket push readiness

Redis Streams can be consumed by a WebSocket manager process that reads from a stream and pushes to connected clients via the same consumer group mechanism. Since we already have Redis in the stack, adding a stream-backed push channel avoids introducing a second persistent connection broker (e.g., a dedicated WebSocket server with Kafka). This simplifies the path to real-time notifications within 2 quarters.

### 8. Operational simplicity

Redis has one binary, one port, one configuration file. Monitoring is done with `INFO`, `LATENCY`, and `SLOWLOG` — commands the team already knows. Kafka requires understanding `server.properties`, topic partitioning, `replication-factor`, `min.insync.replicas`, `acks=all`, ISR management, and broker restart ordering. For a team with no Kafka experience, the cognitive load is disproportionate to the problem's complexity.

---

## Consequences

### Pros

| Property | Impact |
|----------|--------|
| **Fast setup** | Production-ready in <1 week. The existing Redis instance handles the new load. |
| **Zero new infrastructure** | No new servers, no new credentials, no new monitoring. |
| **Low learning curve** | Team already knows Redis. Streams API is 5 commands: `XADD`, `XREADGROUP`, `XACK`, `XPENDING`, `XCLAIM`. |
| **Total ordering** | Notifications within a stream are globally ordered — no partitioning complexity. |
| **PEL-based retry** | Built-in pending-entry tracking maps directly to retry semantics. No custom offset management. |
| **Memory-speed latency** | Sub-millisecond enqueue; notification consumers stay responsive even during bursts. |
| **Natural DLQ pattern** | Dead-letter streams are just other streams — consistent API, no special connector config. |
| **Future WebSocket path** | Same Redis instance serves as the push broker, keeping the stack shallow. |
| **10x headroom** | 100K msg/s capacity vs 2K msg/s projected peak at 10x. |

### Cons

| Property | Impact | Mitigation |
|----------|--------|------------|
| **Memory-bound retention** | Streams live in RAM (or AOF). At 10x, 17M notifications/day at ~1KB each = ~17 GB/day. AOF persistence is slower than disk-native Kafka. | Set `MAXLEN ~ 100000` per stream to cap memory. Acknowledged messages are trimmed. Longer retention can use PostgreSQL archival as a fallback. |
| **No native exactly-once production** | Redis has no idempotent producer like Kafka's `enable.idempotence=true`. Duplicate XADD is possible on network errors. | Produce billing notifications with idempotency keys; the consumer deduplicates against PostgreSQL. At-least-once is acceptable for non-billing notifications. |
| **Manual consumer rebalancing** | Redis Streams does not auto-rebalance consumers when a worker dies. XCLAIM requires explicit monitoring of XPENDING. | Implement a lightweight supervisor (or use Redis's consumer timeout + `XCLAIM`). At our scale, this is ~50 lines of Python, not a distributed systems problem. |
| **No built-in stream processing** | Kafka has Kafka Streams, KSQL, and deep ecosystem for complex event processing. | We don't need stream processing. We need a queue with retry. A Python worker doing `XREADGROUP` → send email/webhook → `XACK` is the right level of complexity. |
| **Sharding for extreme scale** | Beyond ~100K msg/s, Redis Streams requires manual application-level sharding across Redis Cluster nodes. | At 10x traffic (2K events/s), we are 50x below this threshold. If we outgrow Redis Streams, a migration to Kafka is a motivated transition, not an emergency. |

---

## Alternatives Considered

### Apache Kafka

**Why it was rejected:**

Kafka is the superior technology for high-throughput event streaming, long retention, and multi-subscriber fan-out at massive scale. It would be the right choice if we were LinkedIn-sized or building a company-wide event bus. For our constraints, it fails on three counts:

1. **Operational complexity.** A 6-person team with no Kafka experience and no dedicated infrastructure engineer would spend 2-4 weeks just getting a production cluster running — tuning `num.partitions`, `replication.factor`, `min.insync.replicas`, `unclean.leader.election.enable`, and handling ZooKeeper/KRaft failover. This directly violates the 2-week time-to-value constraint.

2. **Zero existing investment.** We already run Redis. Kafka would be a net-new system: new servers, new monitoring, new alerting rules, new backup procedures, new on-call knowledge. For a team of 6, every new system is a significant cognitive and operational tax.

3. **Over-provisioned for the workload.** Kafka excels at millions of messages per second across dozens of topics and hundreds of consumers. We need ~200 events/s across 5-10 notification types. Redis Streams comfortably handles this with a fraction of the complexity. The cost of Kafka (both infra costs and team time) is not justified.

Kafka's edge on exactly-once semantics is also narrow in practice: both systems require idempotent consumers for true end-to-end exactly-once. Kafka's idempotent producer reduces duplicate production, but our application-layer idempotency key approach achieves the same result without depending on broker features.

### Status quo (synchronous HTTP notifications)

Rejected. The synchronous approach has already caused production incidents (connection pool exhaustion, 8s request timeouts, silent failures). Billing notifications have no delivery guarantee. The status quo cannot scale and directly damages product reliability.

### RabbitMQ

Not evaluated in detail. RabbitMQ is a viable general-purpose message broker but introduces a new system (Erlang VM, new deployment, new monitoring) without offering advantages over Redis Streams for this workload. Redis Streams provides equivalent consumer-group semantics with zero new infrastructure. RabbitMQ's AMQP protocol complexity and lack of built-in stream replay (Redis Streams can `XRANGE` from any ID) are further disadvantages for our use case.

---

## Implementation Notes

- Stream naming convention: `notify:{event_type}` (e.g., `notify:task_assigned`, `notify:billing_expired`).
- Each stream uses `MAXLEN ~ 50000` to bound memory growth; acknowledged messages are trimmed.
- Consumer group per notification type (e.g., `notify:email_workers`, `notify:webhook_workers`).
- Background worker pool (Python, `redis-py` + `XREADGROUP` with `BLOCK 2000`).
- Retry: max 3 attempts with exponential backoff (2s, 8s, 32s); final failure moves to `notify:dlq`.
- Billing notification idempotency: `idempotency_key` column in PostgreSQL with unique constraint.
- Monitoring: `XLEN notify:*`, `XPENDING notify:*` metrics exposed to Prometheus via a dedicated endpoint.
