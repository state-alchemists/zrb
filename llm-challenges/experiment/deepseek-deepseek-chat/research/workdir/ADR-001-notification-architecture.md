# ADR-001: Notification Subsystem Architecture

**Status:** Proposed

---

## Context

Our SaaS project management platform (85,000 MAU, ~2M tasks/month, peak 500 req/s) sends email and webhook notifications when tasks are updated, assigned, or completed. The current implementation handles these synchronously inside the Flask HTTP request cycle, causing four systemic problems:

1. **Request timeouts** — average latency of 800ms, spiking to 8s at peak, because notification dispatch blocks the response.
2. **Silent failures** — when email providers or webhook endpoints are unreachable, notifications are dropped with no retry or dead-letter queue.
3. **Cascading failures** — two incidents this year where a slow webhook caused connection pool exhaustion, taking down unrelated endpoints.
4. **No delivery guarantees** — billing-critical notifications (trial expired, payment failed) require exactly-once semantics; the current system offers none.

We need to decouple notification dispatch from the HTTP request cycle with an asynchronous message broker. The solution must support: retry with exponential backoff, at-least-once delivery for general events, exactly-once delivery for billing events, and real-time WebSocket push within two quarters. It must handle 10x traffic growth without re-architecting.

### Constraints

- **Team**: 6 engineers (3 senior, 3 mid-level), no dedicated infrastructure engineer.
- **Existing infrastructure**: Redis already in production (session storage, rate limiting).
- **Team experience**: No Kafka experience; team is proficient with Python, Flask, and the existing Redis stack.
- **Timeline**: Must deliver value within 2 weeks of setup/migration work.
- **Budget**: Modest — cannot afford managed Confluent Cloud at full scale.
- **Requirement**: Exactly-once semantics for billing notifications.

---

## Decision

**Adopt Redis Streams as the notification message broker.**

Redis Streams provides an async message queue with consumer groups, persistence, and retry semantics that directly address our four problems while running on infrastructure we already operate. This decision is contingent on implementing idempotency keys at the producer and consumer layers to satisfy the exactly-once requirement for billing events — Redis Streams does not natively provide exactly-once delivery, but with idempotent consumers the practical effect is identical.

### Architecture Outline

```
HTTP Request → Flask → Redis Streams (producer) → Consumer Workers (Python) → Email/Webhook/WebSocket
                                          ↕
                                Retry Stream (DLQ)
```

- The Flask app writes notification events to a Redis stream (non-blocking, <1ms).
- A pool of background workers (Python, deployed on existing EC2 or as a small ECS service) read from consumer groups, dispatch, and acknowledge.
- Failed deliveries are moved to a retry stream with exponential backoff; persistent failures land in a dead-letter stream for manual review.
- Billing notifications carry idempotency keys (e.g., `{event_type}:{user_id}:{timestamp_hash}`) so consumer-side deduplication achieves exactly-once semantics.

---

## Consequences

### Positive

1. **Zero new infrastructure** — Redis is already running in production for session storage and rate limiting. We add one more logical database (or a small dedicated Redis instance for isolation) using the same deployment playbook and monitoring. No new brokers, no new stateful services to operate.
2. **Sub-millisecond producer writes** — adding a message to a Redis stream is an in-memory operation. The HTTP request cycle drops from ~800ms to <5ms for notification dispatch, eliminating the timeout and connection-pool problems.
3. **Consumer groups for exactly-once processing within the group** — Redis Streams' consumer groups ensure each message is delivered to exactly one consumer in the group. Combined with `XACK`, this gives reliable at-least-once delivery out of the box. No duplicate processing across workers.
4. **Familiar primitives** — the team already uses Redis daily. The `XADD`, `XREADGROUP`, `XACK`, and `XPENDING` commands have straightforward semantics. The Python `redis-py` library supports them natively. Learning curve is low — days, not weeks.
5. **Built-in retry with dead-letter support** — `XPENDING` reveals unacknowledged messages; `XCLAIM` reassigns them to another consumer for retry. A periodic sweep moves expired retries to a dead-letter stream. This solves the silent-failure problem without external infrastructure.
6. **Paves the way for WebSocket push** — Redis Streams + `PUBLISH`/`SUBSCRIBE` are a natural fit for real-time push. The same Redis instance can fan out notification events to WebSocket gateway processes. This meets the two-quarter timeline with minimal additional architecture.
7. **10x scale on the same Redis node** — at 500 req/s peak, with ~1 notification per request, we're at ~500 msg/s. A single Redis instance handles 100k+ msg/s. Even at 10x (5,000 msg/s, 5 million notifications/month), we remain well within the capacity of a `cache.r6g.large` or similar instance. No sharding needed.
8. **2-week delivery** — the core integration (Flask producer + consumer worker + retry logic) can be built and deployed within two weeks. No new infrastructure to provision, no new deployment pipelines, no schema registry, no topic governance.

### Negative

1. **No native exactly-once delivery** — Redis Streams guarantees at-least-once delivery. A consumer may process a message and crash before `XACK`ing it, causing redelivery. We must implement idempotency at the consumer (deduplication via idempotency keys stored in Redis or PostgreSQL). This is well-understood but adds a layer we must build and test.
2. **In-memory storage limits retention** — Redis stores streams in memory. If we need weeks of message retention for replay or audit, memory costs grow linearly. For the notification use case (messages consumed within seconds to minutes), this is manageable. We can use `MAXLEN ~ N` to cap stream size and `XTRIM` for housekeeping. If long-term audit trails are needed, archive to S3 via a separate process.
3. **Single-node bottleneck** — Our existing Redis deployment is a single primary (with a replica for failover). At very high throughput or if we add many consumer groups, the primary becomes a bottleneck. At 10x our current traffic (~5k msg/s), this is not a concern. If we outgrow it, we can scale to Redis Cluster, but that adds significant operational complexity.
4. **No partition-based parallelism** — Redis Streams consumers within a group compete for messages; there's no partitioning model like Kafka's. If a single consumer is slow, it can block message processing for that group. Mitigation: use multiple consumers and tune concurrency, or shard across multiple streams by notification type (e.g., `stream:email`, `stream:webhook`, `stream:billing`).
5. **No built-in stream processing** — Unlike Kafka's Kafka Streams or ksqlDB, Redis Streams has no stream-processing DSL. Complex event transformation requires writing Python consumer logic. For our use case (dispatch to email/webhook/WebSocket), this is straightforward and doesn't warrant stream processing infrastructure.

---

## Alternatives Considered

### Apache Kafka (Self-Hosted or AWS MSK)

**Why it was rejected:**

1. **Operational complexity exceeds team capacity** — Kafka requires dedicated brokers, ZooKeeper (or KRaft), topic configuration, partition tuning, consumer offset management, and ongoing monitoring of ISR counts, consumer lag, and disk usage. With a 6-person team and no dedicated infrastructure engineer, this is a net-negative on velocity. Every Kafka incident is a multi-hour investigation for engineers who don't work with it daily. The AxonOps report notes that "managed Kafka removes some broker lifecycle work, but your team still owns topic governance, client behavior, consumer lag, quotas, ACLs, schema lifecycle, and the mechanics of incident response."

2. **Budget constraints** — Managed Confluent Cloud is explicitly ruled out by the budget constraint. AWS MSK at our scale would cost ~$300-800/month for a small 3-broker cluster, not including data transfer and storage costs. For a team with a modest budget, this is non-trivial for a single subsystem. Self-hosting Kafka on EC2 shifts the cost to engineering hours — estimates suggest a team would need at least 10 people just to manage Kafka operations, according to one Confluent customer report.

3. **2-week timeline is infeasible** — Deploying Kafka (even on MSK), configuring topics, setting up schema validation, writing producer/consumer clients with the Kafka Python library, establishing monitoring for consumer lag and broker health, and integrating with the existing Flask monolith cannot be done in two weeks for a team with zero Kafka experience. A realistic estimate is 4-6 weeks before delivering production value.

4. **Overkill for the throughput requirements** — Kafka excels at millions of messages per second, multi-subscriber fan-out, long-term storage, and replay. Our peak is 500 msg/s with a few consumer types. Kafka's partitioning, offset management, and replication model add complexity without providing proportional benefit at this scale. Redis Streams comfortably handles this throughput with a fraction of the operational surface area.

5. **Team knowledge gap** — Zero team members have Kafka experience. Adding Kafka means learning a new stack (brokers, ZooKeeper/KRaft, topic design, partitioning strategy, consumer groups, Kafka Connect, Schema Registry) while simultaneously learning how to operate it. Redis Streams builds on skills the team already has.

**When Kafka would be the right choice:** If throughput exceeds 50k msg/s, if we need multi-year message retention with replay, if we need exactly-once semantics across multiple downstream systems natively (Kafka's transactional API + idempotent producer), or if the notification subsystem evolves into a full event-sourced platform with many consumers. At that point, the operational investment is justified by the scale and complexity. We can migrate from Redis Streams to Kafka with a well-defined adapter layer; the consumer interface (read from stream, process, acknowledge) is structurally similar.

### RabbitMQ

**Why it was rejected:** RabbitMQ is a strong contender but adds a new Erlang-based runtime we don't operate, requires new deployment and monitoring tooling, and doesn't offer stream semantics (consumer groups, message replay, offset tracking) as naturally as Redis Streams or Kafka. RabbitMQ's AMQP model (exchanges, bindings, queues) introduces routing complexity we don't need for a simple dispatch queue — we want a stream we can consume from multiple workers with acknowledgment, not a complex routing topology.

### Amazon SQS + SNS

**Why it was rejected:** SQS provides at-least-once delivery with a dead-letter queue and requires no operational overhead. However, it has three significant drawbacks for our use case: (1) no consumer groups — each SQS queue is pull-based and messages are hidden, not tracked by consumer; scaling consumers requires careful tuning of visibility timeouts and can lead to duplicates. (2) No real-time push — SQS is pull-only (long polling), which adds latency for WebSocket fan-out plans. SNS + SQS fan-out is possible but adds cost and complexity. (3) Vendor lock-in — if we ever need to migrate off AWS or run in multiple regions, SQS introduces tight coupling. Redis Streams keeps us on open-source infrastructure with a clear migration path to Kafka or other brokers if needed.

---

## Summary

| Criterion | Redis Streams | Apache Kafka |
|---|---|---|
| Existing ops knowledge | **High (already run Redis)** | None — new skill |
| Setup time | **<2 weeks** | 4-6 weeks minimum |
| Throughput at our scale | **100k+ msg/s per node** | Millions — overkill |
| Consumer groups | **Native (within group)** | Native (across partitions) |
| Exactly-once semantics | Requires idempotent consumer | Native (transactional API) |
| Message retention | **Memory-bound (capped)** | Disk-based (long retention) |
| Operational complexity | **Minimal (one more Redis DB)** | High (brokers, KRsft, monitoring) |
| Budget impact | **~$0 marginal (existing Redis)** | $300-800+/month (MSK) |
| WebSocket path | **Natural (Pub/Sub on same Redis)** | Requires separate WebSocket broker |

Redis Streams is the correct choice for our current scale, team composition, and timeline. The trade-off — consumer-level idempotency for exactly-once semantics — is well-understood and straightforward to implement with idempotency keys stored in Redis or PostgreSQL. We should revisit this decision if our message throughput exceeds 50k msg/s or if the notification subsystem evolves into a platform-wide event backbone requiring native exactly-once across multiple consumers.
