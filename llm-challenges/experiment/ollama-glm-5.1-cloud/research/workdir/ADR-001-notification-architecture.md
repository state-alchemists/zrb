# ADR 001 — Notification Subsystem Message Broker

- **Status**: Proposed
- **Date**: 2026-05-17
- **Deciders**: Engineering team (6 engineers, 3 senior / 3 mid-level)
- **Context tags**: notifications, async-processing, infrastructure, scaling

## Context

Our SaaS project management platform (85k MAU, ~2M tasks/month, ~500 req/s peak) handles notifications — emails, webhooks, and upcoming WebSocket pushes — synchronously inside the HTTP request cycle. This causes request timeouts (800ms avg, 8s spikes), silent failures with no retry or dead-letter queue, and cascading failures where slow external endpoints exhaust the database connection pool and take down unrelated features. Two such incidents occurred this year.

Billing-critical notifications ("trial expired", "payment failed") currently have no delivery guarantee; they must be delivered exactly once.

We need to decouple notification processing from the request cycle, add retry with exponential backoff, guarantee at-least-once delivery (exactly-once for billing), support real-time WebSocket push within 2 quarters, and absorb 10x traffic growth without re-architecting.

The team has 6 engineers, no dedicated infrastructure person, and no Apache Kafka experience. Redis is already in production for session storage and rate limiting. The budget cannot support managed Confluent Cloud at scale. The solution must deliver value within 2 weeks of starting migration.

## Decision

> We will use Redis Streams as the message broker for the notification subsystem.

Redis Streams builds on infrastructure the team already operates and understands, delivers a working async notification pipeline within the 2-week constraint, and provides sufficient throughput, ordering, and consumer-group semantics for current and projected load. Exactly-once delivery for billing notifications will be achieved through an application-level idempotency layer backed by PostgreSQL, not through broker-level transactional semantics.

## Rationale

### Throughput is well within Redis Streams' capacity

Current peak is ~500 req/s. Even under a generous assumption that every request produces a notification, that is ~500 messages/s. Redis Streams on a single node handles ~100k messages/s. The 10x growth target (~5k messages/s) remains trivial for Redis. Kafka's advantage of multi-million msg/s throughput is irrelevant — we will never approach the ceiling where Redis Streams becomes a bottleneck.

### Operational complexity matches the team

We have no Kafka experience and no dedicated infrastructure engineer. Operating Kafka — even AWS MSK — requires understanding partition assignment, consumer group rebalances, offset management, replication factor tuning, and monitoring (lag, under-replicated partitions). This operational surface area is unjustifiable for 6 engineers who need to ship product features. Redis Streams adds one data structure to an already-running Redis instance the team knows how to debug, back up, and monitor.

### Time to value is days, not weeks

Because Redis is already deployed and the team is familiar with its operations, the path to a working producer/consumer pipeline is: create a stream, write to it from Flask (`XADD`), read from it in a consumer process (`XREADGROUP`), and ack on success (`XACK`). No new infrastructure to provision, no broker cluster to configure, no security ACLs to set up between services. This fits within the 2-week constraint. Kafka would require at minimum: infrastructure provisioning, broker configuration, topic schema design, producer/client library integration, and team training — none of which deliver user-facing value in that window.

### Exactly-once for billing is achievable at the application layer

Neither Kafka nor Redis Streams delivers true exactly-once semantics without application cooperation. Kafka's transactional exactly-once (idempotent producer + transactional consumer) requires careful configuration of `enable.idempotence`, `transactional.id`, `isolation.level=read_committed`, and consumer offset commit strategy. It is frequently misconfigured and does not prevent duplicate processing across consumer restarts if offsets are committed before processing completes.

For our specific use case — billing notifications that must never be duplicated — the simpler and more reliable approach is: produce messages with a deterministic ID (`{tenant_id}:{event_type}:{entity_id}`), write a deduplication record to PostgreSQL before processing (INSERT ... ON CONFLICT DO NOTHING), and process only if the insert succeeds. This gives effective exactly-once with Postgres as the source of truth, which we already trust and operate. The deduplication table doubles as an audit log for billing events.

### Message retention is sufficient

Redis Streams supports `MAXLEN` trimming and time-based eviction via `MINID`. Notification messages have short useful lifetimes — once processed, they consume no further value beyond a brief retry window. A 7-day retention with `MAXLEN ~ 1M` covers the retry-with-backoff window and stays well within memory budget. Kafka's persistent log is over-engineered for ephemeral notification events; we persist what matters (billing audit trail) in PostgreSQL, not in the message broker.

### Consumer groups are native

Redis 5.0+ supports `XREADGROUP`, `XPENDING`, `XCLAIM` for consumer group semantics: partitioned consumption, pending-entry recovery on consumer failure, and explicit acknowledgement. This covers the retry and failure-detection requirements without custom coordination logic.

### WebSocket push is a natural extension

The upcoming WebSocket feature requires a fan-out mechanism. Redis Pub/Sub alongside Streams handles this: produce to a Stream for durable processing (email, webhook), publish to a channel for real-time push. Both run on the same Redis instance. Kafka would require the same pattern with a separate mechanism (e.g., WebSocket server subscribing to a dedicated topic), but the operational overhead is heavier.

## Alternatives Considered

- **Apache Kafka** — Rejected. Kafka's strengths (persistent log, massive throughput, multi-topic ecosystem, transactional exactly-once) do not compensate for its operational burden given our constraints. We would choose Kafka if: our message rate exceeded ~50k msg/s, we needed multi-service event sourcing with months-long retention, we had a dedicated platform/infra team, or we had already budgeted for managed Kafka (MSK or Confluent). None of these apply today. Adding Kafka now would consume the 2-week window on infrastructure setup before delivering any user-facing improvement. We could revisit this decision if traffic grows beyond what a Redis Cluster can handle (roughly 500k+ msg/s sustained), or if we adopt an event-sourcing architecture across multiple services.

- **PostgreSQL LISTEN/NOTIFY + queue tables** — Rejected. `NOTIFY` has no persistence (lost on restart), no consumer groups, and no built-in retry. Queue tables in Postgres would work for at-least-once but add load to the primary database that is already a bottleneck (cascading failures from connection pool exhaustion). This approach increases coupling to the database rather than decoupling from it.

- **RabbitMQ / AWS SQS** — Not evaluated in depth. RabbitMQ adds a new operational component without the team familiarity that Redis has. SQS introduces a cloud-specific dependency and higher per-message cost at scale; it also lacks in-process consumer group semantics for our monolith architecture without additional orchestration.

## Consequences

### Positive

- **Fast delivery**: Working async notification pipeline within days, not weeks. The team can decouple notifications from HTTP requests immediately, resolving the timeout and cascading-failure problems.
- **Low operational cost**: No new infrastructure to provision, monitor, or learn. Redis Streams uses the existing Redis instance (with separate logical databases or key namespacing to isolate from session/rate-limit data).
- **Sufficient headroom**: Single-node Redis handles 10x current peak load comfortably. Redis Cluster or Redis Enterprise provides a scaling path if growth exceeds single-node capacity.
- **Natural WebSocket path**: Redis Pub/Sub provides real-time fan-out alongside Streams for durable processing, on the same instance.
- **Effective exactly-once**: Application-level idempotency with PostgreSQL is simpler to reason about than Kafka's transactional consumer protocol, and produces an audit trail as a side effect.

### Negative

- **Redis is not a persistent log**: Stream data lives in memory (with optional AOF/RDB persistence). A catastrophic Redis data loss could lose in-flight notifications. We mitigate this by: (1) Redis AOF persistence enabled with `appendfsync everysec`, (2) critical billing events are written to the PostgreSQL deduplication table before acknowledgement, making Postgres the authoritative record, not Redis.
- **Single-node scaling ceiling**: A single Redis node handles our projected load, but if the platform grew beyond ~500k msg/s sustained, we would need Redis Cluster or a migration to Kafka. This decision should be revisited if MAU exceeds ~1M with high notification density.
- **No native dead-letter queue**: Redis Streams do not auto-create DLQs. We must implement this ourselves: after N failed deliveries, move the message to a `notifications:dead` stream and alert. This is straightforward (~50 lines of consumer logic) but is custom code rather than a built-in feature.
- **Monitoring gap**: Redis Streams lack Kafka's rich ecosystem of monitoring tools (Burrow, Kafka lag exporter). We will need to build consumer-lag monitoring using `XPENDING` and custom metrics exported to our existing observability stack (Prometheus/Grafana or equivalent).
- **No schema registry**: Kafka's Confluent Schema Registry enforces message contracts across producers and consumers. With Redis Streams, message format is implicit. We mitigate this with: (1) a typed Python `NotificationEvent` dataclass that serializes to JSON, (2) a version field in every message, (3) consumer-side validation and graceful degradation for unknown versions.

### Follow-ups

1. **Define the notification event schema** — Create a `NotificationEvent` dataclass with version, type, tenant_id, entity_id, and payload fields. All producers use it; all consumers validate against it.
2. **Implement the idempotency layer** — PostgreSQL table `notification_dedup (id_hash PK, created_at, status)` with `INSERT ... ON CONFLICT DO NOTHING`. Billing notifications must go through this layer.
3. **Implement consumer with retry and DLQ** — Worker process using `XREADGROUP`, exponential backoff via `XCLAIM` with `idle` check, and `notifications:dead` stream for messages exceeding max retries.
4. **Add consumer-lag monitoring** — Poll `XPENDING` on a timer, expose as Prometheus gauge, alert when lag exceeds threshold.
5. **Isolate Redis for Streams** — Use a dedicated Redis database index (or separate instance) for Streams to avoid memory pressure on session/rate-limit data. Set `maxmemory-policy noeviction` on the Streams database.
6. **Load test at 10x** — Validate that a single Redis node handles 5k msg/s with consumer groups, AOF persistence enabled, under sustained load. Document the ceiling before Redis Cluster becomes necessary.
7. **Revisit this ADR** — If MAU exceeds 500k or notification volume exceeds 100k msg/s sustained, evaluate Kafka as the next evolution. The Stream-based consumer interface should be abstracted behind a `MessageBroker` protocol to make this swap feasible.