# ADR-001: Notification Subsystem Architecture

**Status:** Proposed

---

## Context

The Notifier subsystem in our SaaS project management platform currently sends emails and webhooks synchronously inside the HTTP request cycle. With ~500 req/s peak and ~2M tasks/month, this coupling produces four concrete problems:

1. **Request timeouts** — average 800ms latency, spiking to 8s at peak.
2. **Silent failures** — no retry, no dead-letter queue when downstream endpoints fail.
3. **Cascading failures** — slow webhook endpoints exhaust database connection pools, taking down unrelated features (two incidents in the past year).
4. **No delivery guarantees** — billing-critical notifications (trial expiry, payment failure) require exactly-once delivery; the current path provides exactly-once in name only.

The new subsystem must address all four while supporting WebSocket push (target: 2 quarters out) and 10x traffic growth. Key constraints shape the choice:

| Constraint | Detail |
|---|---|
| Team size | 6 people (3 senior, 3 mid-level), no dedicated infrastructure engineer |
| Existing infra | Redis in production today (session storage, rate limiting) |
| Team experience | Zero Kafka experience; strong Redis familiarity |
| Time to value | Must deliver measurable improvement within 2 weeks |
| Budget | Modest; managed Confluent Cloud is out of reach at full scale |
| Delivery guarantees | Exactly-once for billing events; at-least-once for everything else |

---

## Decision

**Adopt Redis Streams** as the notification backbone.

All notification-producing code (task update, assignment, completion handlers) will `XADD` a structured event to a Redis stream. A set of lightweight Python workers (running in the same deployment unit or as sidecars) will `XREADGROUP` from consumer groups, dispatch to the appropriate channel (email provider, webhook endpoint), and acknowledge (`XACK`) on success. Failed deliveries are retried with exponential backoff via a pending-entries list (`XPENDING`); entries that exceed the retry budget are moved to a dead-letter stream for manual inspection.

### Justification

**Operational leverage is the decisive factor.** We already run Redis in production. The team knows its failure modes, its monitoring, its backup strategy. Introducing Kafka would require standing up a new stateful cluster (Zookeeper or KRaft), learning its partitioning model, tuning its JVM heap, and building operational runbooks from scratch — work that a 6-person team with no dedicated infra engineer cannot absorb in 2 weeks. Redis Streams delivers the core async-decoupling value on day one using a system the team already operates.

**Throughput and scale are not a concern at our projected load.** Redis Streams handles 50k–100k messages/second on a single node. Our peak is 500 req/s today (each request producing 1–3 notifications); at 10x growth that is 5k req/s and ~15k notifications/second — well within the headroom of a modest Redis instance, especially if we provision a dedicated Redis node for streams (our recommendation below).

**Exactly-once semantics are achievable through application-level idempotency.** Redis Streams provides at-least-once delivery natively (same as Kafka's default `enable.idempotence=false`). For billing-critical notifications, we assign an idempotency key (derived from `event_type + entity_id + sequence_number`) and record processed keys in a separate Redis set with a TTL or in PostgreSQL. This pattern is straightforward, well-documented, and avoids depending on Kafka's transaction coordinator protocol — a complex feature that even experienced Kafka teams frequently misconfigure.

**WebSocket push lands cleanly.** Redis Pub/Sub (or a secondary stream) can fan out notifications to WebSocket servers. The same Redis instance serves both streams and pub/sub, keeping the infrastructure surface small.

---

## Consequences

### Pros

1. **Low operational delta.** Redis is already monitored, backed up, and understood. No new cluster type, no new port, no new JVM to tune. A dedicated Redis node for streams costs ~$30–60/month on AWS ElastiCache.

2. **Fast time-to-value.** A working prototype (Flask handler → `XADD` → worker → email dispatch with retry) can be built, tested, and deployed in under a week. Well within the 2-week constraint.

3. **Simple consumer group model.** `XREADGROUP` with auto-balancing (`>`) means workers self-distribute — no partition assignment protocol to learn. Adding or removing workers during a traffic spike is safe and immediate.

4. **Sub-millisecond append latency.** `XADD` completes in <1ms typically, compared to Kafka's ~2–5ms round-trip to the partition leader. This keeps HTTP response time low even if the producer writes the event inline (though we recommend a background thread or Celery task to keep the HTTP path truly unblocked).

5. **Message retention with bounded memory.** `MAXLEN ~ 100000` trims the stream to an approximate size, preventing unbounded memory growth while keeping enough history for replay and debugging.

6. **Dead-letter channel built on the same primitive.** Failed messages after `max_retries` are `XADD`-ed to a `dlq:notifications` stream. The same tooling (consumer groups, `XREADGROUP`) applies.

7. **WebSocket path is natural.** Redis Pub/Sub is the standard pattern for multi-server WebSocket fan-out. No extra broker needed.

### Cons

1. **No native exactly-once delivery.** Unlike Kafka's transaction coordinator + idempotent producer, Redis Streams does not provide exactly-once as a protocol primitive. We must implement idempotency-key deduplication ourselves. This is manageable for billing events (~hundreds/day) but adds a small per-event check overhead.

2. **Memory-bound retention.** Streams live in RAM (optionally persisted to RDB/AOF). Large retention windows for replay-heavy workflows are expensive. We mitigate with `MAXLEN` trimming and by archiving completed events to PostgreSQL cold storage daily.

3. **No partition rebalancing protocol.** If a consumer in a group crashes, its pending entries remain unprocessed until another consumer claims them via `XCLAIM` or `XAUTOCLAIM`. Kafka's rebalance protocol handles this automatically. We mitigate with a short `CLAIM` interval (e.g., `XAUTOCLAIM 60000` — stale entries reassigned after 60 seconds).

4. **Single-node throughput ceiling.** Redis is single-threaded for commands (multi-threaded for I/O). Above ~100k msg/s a single node becomes a bottleneck. At our projected 15k msg/s at 10x growth this is safe, but if traffic unexpectedly exceeds 5–10x the projection, we would need Redis Cluster or a sharding layer — neither is as mature as Kafka's native partitioning.

5. **No exactly-once semantics across stream + database.** If the worker commits a database transaction then crashes before `XACK`, the event is reprocessed. This is an at-least-once gap. Mitigation: design workers to be idempotent in their side effects (e.g., "upsert" the notification record in PostgreSQL, or include an idempotency check on every retry).

6. **Smaller community and tooling ecosystem.** Kafka has Confluent Schema Registry, Kafka Connect, KSQL, MirrorMaker, and extensive monitoring dashboards. For Redis Streams, observability is more DIY — `XLEN`, `XINFO STREAM`, `XPENDING` are the primitives.

---

## Alternatives Considered

### Apache Kafka (rejected)

Kafka is technically superior for the general case: durable log-based storage, native exactly-once semantics, automatic consumer rebalancing, multi-tenancy through partitions, and throughput scaling to millions of messages/second. However, it fails decisively against our constraints.

- **Operational complexity.** A Kafka cluster requires careful JVM tuning (heap, GC), disk configuration (separate disks for log segments), topic/partition sizing, and monitoring of ISR (in-sync replica) counts, under-replicated partitions, and consumer lag. For a 6-person team with no dedicated infra engineer, this is a significant ongoing tax. Two weeks is not enough time to learn Kafka's failure modes well enough to run it safely in production — it takes teams months of pager rotations to build that intuition.

- **Time-to-value.** Standing up a production-grade Kafka cluster (even on AWS MSK) and wiring the first notification event through it cannot be done within 2 weeks alongside existing feature work. The learning curve alone (partitions, offsets, consumer groups, exactly-once semantics with transactions) exceeds the timeline.

- **Budget mismatch.** Managed Confluent Cloud at our projected 15k msg/s is $500–1,500/month. Self-hosted Kafka on EC2/MSK Starter would be cheaper (~$100–200/month) but then the operational burden returns. Redis Streams on a dedicated ElastiCache node costs ~$30–60/month — an order of magnitude less.

- **Overkill for current scale.** Kafka is designed for systems processing millions of events/second across dozens of microservices. Our current peak is 500 req/s. Even at 10x growth (5k req/s), Redis Streams handles the load comfortably. Introducing Kafka at this stage is premature optimization that trades simplicity for power we will not use for at least 2–3 years.

The one scenario where Kafka would win is if we were already a Kafka shop or had an infrastructure engineer. Neither is true.

### RabbitMQ (rejected, lower priority)

RabbitMQ offers a mature AMQP-based queueing model with dead-letter exchanges, TTL, and flexible routing. It is simpler to operate than Kafka and has better at-least-once support out of the box than Redis Streams. However:

- It introduces a new stateful service (Erlang VM, management plugin, clustering) — the same "new infrastructure" problem as Kafka, albeit with less complexity.
- It lacks the consumer group abstraction for competing-consumer patterns. Each queue is consumed round-robin; scaling requires manual `exclusive` queues or shovels.
- Stream replay is not native. RabbitMQ Streams (a separate plugin) addresses this but is newer and less battle-tested.
- Message ordering is preserved within a queue, but not across queues for the same event type. Redis Streams preserves ordering within a stream partition naturally.
- We already run Redis. Introducing RabbitMQ would add an infrastructure surface with no offsetting benefit over the Streams approach.

Redis Streams provides the same competing-consumer pattern (consumer groups), retry mechanics (pending entries), and dead-letter capability with zero new infrastructure.

---

## Migration Plan Summary

| Phase | Timeline | Deliverable |
|---|---|---|
| **Phase 1** | Week 1 | Dedicated Redis node (ElastiCache), producer decorator (`XADD` on task events), single worker with email dispatch + `XACK` |
| **Phase 2** | Week 2 | Retry with exponential backoff (`XAUTOCLAIM`), dead-letter stream, health check endpoint (`XLEN`, consumer lag) |
| **Phase 3** | Month 2 | WebSocket push via Redis Pub/Sub, idempotency-key deduplication for billing events |
| **Phase 4** | Month 3 | Cold-archive completed events to PostgreSQL, Grafana dashboard for stream metrics |
