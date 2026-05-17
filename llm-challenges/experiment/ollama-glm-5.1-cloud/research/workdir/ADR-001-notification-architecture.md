# ADR 001 — Notification Subsystem Message Broker

- **Status**: Proposed
- **Date**: 2026-05-17
- **Deciders**: Backend team (3 senior, 3 mid-level engineers)
- **Context tags**: notifications, async-processing, messaging, reliability

## Context

Our SaaS project management platform (85k MAU, ~2M tasks/month, peak ~500 req/s) currently sends all notifications — emails and webhooks for task updates, assignments, completions, and billing events — synchronously inside the HTTP request cycle. This causes request timeouts (800ms average, 8s spikes), silent delivery failures with no retry or dead-letter queue, and cascading connection-pool exhaustion when downstream endpoints are slow. Two production incidents this year resulted from slow webhook endpoints taking down unrelated features.

We need to decouple notification processing from the request cycle and satisfy these requirements:

- **Async processing** — notifications must not block HTTP responses.
- **Retry with exponential backoff** — transient failures in email providers and webhook endpoints must be retried.
- **At-least-once delivery for all events; exactly-once for billing notifications** — "trial expired" and "payment failed" must never be silently dropped or sent in duplicate.
- **WebSocket push notifications** — real-time delivery within 2 quarters.
- **10x traffic headroom** — the chosen system must handle ~5,000 req/s peaks without re-architecting.

Hard constraints on the decision:

- 6-person engineering team with no dedicated infrastructure engineer.
- Redis is already in production (sessions, rate limiting). The team is comfortable operating it.
- No one on the team has Kafka operations or application experience.
- Time to first value must be under 2 weeks.
- Budget is modest — managed Confluent Cloud at scale is not affordable.

## Decision

> We will use Redis Streams as the message broker for the notification subsystem.

Redis Streams (XADD, XREADGROUP, XACK, XPENDING) give us partitioned consumer groups, persistent message storage, and at-least-once delivery out of the box — on infrastructure the team already operates. Exactly-once delivery for billing notifications will be achieved through application-level idempotency: every billing notification carries a deterministic `notification_id`; before processing, the worker persists this ID in a PostgreSQL `processed_notifications` table inside the same transaction as the side effect. Duplicate deliveries from Redis Stream re-deliveries are detected and discarded by unique constraint on that table. This is a well-understood pattern that does not require broker-level transaction support.

Kafka is the stronger product for high-throughput, multi-consumer event streaming at scale, but its operational weight — ZooKeeper/KRaft clusters, broker configuration, partition rebalancing, monitoring — is disproportionate for a notification pipeline at our volume and with our team composition.

## Consequences

### Positive

- **Zero new infrastructure** — Redis is already running in production with monitoring, alerting, and on-call runbooks. Adding Streams is a feature enablement, not a new service rollout.
- **Fast time to value** — a Flask worker consuming from a Stream with XREADGROUP can be in production within days, not weeks. The 2-week constraint is achievable with margin.
- **Sufficient throughput** — Redis Streams handle hundreds of thousands of messages per second on a single instance. Our peak of ~500 req/s (even at 10x, ~5,000 req/s) is well within one Redis node's capacity, with room to add read replicas for the WebSocket fan-out phase.
- **Consumer groups** — XGROUP/XREADGROUP provide the group-based consumption model needed for parallel workers, with XACK-based delivery tracking and XPENDING for retry inspection.
- **Exactly-once for billing via idempotency** — the PostgreSQL deduplication table pattern is simple to implement, test, and reason about. It couples delivery correctness to a database the team already operates, not to a broker transaction API.
- **Lower operational risk** — fewer moving parts means fewer 3am pages. One Redis cluster, one PostgreSQL, one set of Flask workers.

### Negative

- **Message retention is capacity-bound** — Redis holds streams in memory (with optional AOF/RDB persistence). At our 10x growth target, raw message volume is manageable (~10–50 GB with sensible MAXLEN policies), but the team must set and monitor `MAXLEN` per stream to prevent unbounded memory growth. Kafka's disk-based retention is more forgiving here.
- **No native exactly-once at the broker level** — we are committing to the application-level idempotency pattern for exactly-once delivery. If the notification surface area grows beyond billing events into financial transaction records, the deduplication table approach becomes a coupling point and should be revisited.
- **Single-node availability** — our current Redis is a single instance (with replica). A Streams failure blocks all notification processing. Kafka's replicated partitions provide stronger availability guarantees per partition. Mitigation: Redis Sentinel or Cluster mode for automatic failover, which the team can adopt incrementally.
- **Limited fan-out for future consumers** — Redis Streams support consumer groups, but each consumer group processes each message once. If we later need independent services to independently consume the same event stream (e.g., an analytics pipeline alongside notifications), we add a consumer group per service, and each group's pending entries are tracked independently. Kafka's topic model makes multi-consumer patterns more natural, but this is not a near-term requirement.
- **Operational monitoring gap** — Redis Streams lack the mature consumer-lag dashboards and dead-letter tooling that the Kafka ecosystem provides. We will need to build lightweight monitoring on XPENDING/XINFO.

### Follow-ups

- Implement `processed_notifications` table with a unique constraint on `(notification_type, notification_id)` as the idempotency gate for billing events.
- Set `MAXLEN ~100,000` on notification streams to cap memory while retaining enough backlog for reprocessing.
- Add Redis Sentinel for automatic failover before the WebSocket push notification phase.
- Build a small monitoring dashboard on XPENDING/XINFO for consumer lag and stuck-message alerting.
- Evaluate Kafka adoption if and when we need a general-purpose event bus spanning multiple services — that is a different problem than notification delivery.

## Alternatives Considered

### Apache Kafka

Kafka provides strict per-partition ordering, durable disk-based retention, replicated partitions for fault tolerance, native exactly-once semantics via idempotent producers and transactional consumers, and a rich ecosystem of tooling (Schema Registry, Connect, consumer lag dashboards). It is the correct choice for a general-purpose event mesh serving many independent consumer teams.

We rejected it for this decision because:

- **Operational complexity is too high for a 6-person team with no Kafka experience.** Running Kafka in production (even KRaft mode without ZooKeeper) requires expertise in broker sizing, partition strategy, offset management, and compaction tuning. No one on the team has this knowledge, and there is no dedicated infrastructure engineer to own it.
- **Time-to-value exceeds the 2-week constraint.** Learning Kafka internals, standing up a cluster, configuring monitoring, and implementing transactional consumers would take 4–6 weeks minimum for this team.
- **Managed Kafka (Confluent Cloud) is out of budget** at our projected scale, and still requires application-level expertise to use correctly.
- **Throughput is overspecced for our problem.** Kafka's design point is millions of messages per second, multi-tenant consumer isolation, and long-lived event replay. Our notification pipeline peaks at hundreds of messages per second and needs at-most-minutes retention. This is over-engineering by an order of magnitude.
- **We would have chosen Kafka if**: we had a dedicated platform/infrastructure engineer, our throughput target exceeded 100k msg/s, or we needed a general event bus for 5+ independent consumer teams. None of these are true today.

### PostgreSQL LISTEN/NOTIFY (considered and dismissed)

Mentioned for completeness. LISTEN/NOTIFY is fire-and-forget with no persistence, no consumer groups, and no replay — it cannot satisfy the at-least-once or retry requirements.

### PostgreSQL as a queue (considered and dismissed)

Using a `notifications` table with `FOR UPDATE SKIP LOCKED` is viable at our scale and provides exactly-once via transactional guarantees. We dismissed it because: polling introduces latency; it couples queue logic to the primary database under heavy notification volume; and it does not generalize to the WebSocket fan-out pattern we need in 2 quarters. Redis Streams provide a purpose-fit primitive with comparable correctness when combined with application-level deduplication.