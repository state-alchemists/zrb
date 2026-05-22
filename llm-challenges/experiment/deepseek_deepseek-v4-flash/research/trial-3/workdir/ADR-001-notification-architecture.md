# ADR-001: Notification Subsystem Architecture

**Status:** Proposed

## Context

The Notifier subsystem in our SaaS project management platform sends emails, webhooks, and (planned) WebSocket push notifications when tasks are created, updated, assigned, or completed. It currently runs synchronously inside the Flask HTTP request cycle, which has produced four systemic failures:

- **Request timeouts**: Average response latency is 800 ms; spikes to 8 s during peak hours because notification delivery blocks the HTTP response.
- **Silent failures**: External email providers or webhook endpoints that are unreachable cause the notification to be dropped with no retry, no dead-letter queue, and no operator signal.
- **Cascading failures**: Two incidents this year where an unresponsive webhook endpoint exhausted the connection pool, rendering unrelated features unavailable.
- **No delivery guarantees**: Billing-critical notifications (trial expiry, payment failure) must be delivered at-least-once or exactly-once; the current system provides neither.

We need an asynchronous notification pipeline that decouples delivery from the request cycle, supports retry with exponential backoff, guarantees at-least-once delivery for billing events (exactly-once where feasible), enables real-time WebSocket push within two quarters, and scales to 10x current traffic without re-architecting.

**Current metrics:** 85,000 MAU, ~2M tasks/month, ~500 req/s peak. Infra: 4 web servers, PostgreSQL (one read replica), Redis in use for sessions and rate limiting. **Team:** 6 engineers (3 senior, 3 mid), no dedicated infrastructure engineer. **Budget:** modest — managed Confluent Cloud is ruled out.

## Decision

**We will use Redis Streams for the notification subsystem.** Notification producers will write events to Redis Streams; a set of consumer workers will read from consumer groups, dispatch to the appropriate channel (email, webhook, future WebSocket), acknowledge on success, and retry on failure with exponential backoff. Idempotent consumer logic with a lightweight deduplication layer will provide effectively-exactly-once semantics for billing notifications.

This decision is driven by three binding constraints:

1. **Operational capacity.** A 6-person team with no dedicated infra engineer cannot absorb the operational cost of a Kafka cluster — node provisioning, ZooKeeper/KRaft management, topic tuning, partition rebalancing, monitoring, and failover procedures. Redis Streams impose zero new infrastructure: we already run Redis in production.

2. **Time-to-value.** We can ship a working notification pipeline in week 1 and declare it production-ready by week 2. Kafka, even on a managed service, would require 2–3 weeks for cluster setup, topic design, consumer-group onboarding, and safety training before the team ships a single notification.

3. **Scale fit.** Redis Streams handle 100,000+ messages per second on modest hardware. Our peak is 500 req/s today; 10x growth yields 5,000 req/s — well within Redis Streams' comfortable range. We are not building a global event backbone that demands Kafka's horizontal throughput ceiling.

### Architecture Overview

```
HTTP Request → Flask handler → XADD (stream:notifications)
                                    │
                          ┌─────────▼──────────┐
                          │  Redis Streams      │
                          │  (consumer groups)  │
                          └─────────┬──────────┘
                          ┌─────────▼──────────┐
                          │  Worker Pool        │
                          │  (XREADGROUP loop)  │
                          └──┬──────┬──────┬───┘
                             │      │      │
                        email  webhook  WebSocket (Q2)
```

- **Producer side (Flask):** After the HTTP handler completes its core logic, it calls `XADD stream:notifications * <event>`. This is non-blocking (< 1 ms). The HTTP response is no longer held hostage by delivery latency.
- **Consumer side (Python workers):** A pool of workers runs `XREADGROUP` in a blocking loop. On success (email sent, webhook 200), they issue `XACK`. On transient failure, the message remains pending and is retried with exponential backoff via `XCLAIM` on a retry-consumer group with a different visibility timeout.
- **Dead-letter queue:** Messages that exceed the retry cap are `XADD`'ed to `stream:notifications:dead-letter` and surfaced to operators via a health-check endpoint.
- **Exactly-once for billing:** Billing consumers apply idempotency keys stored in Redis (via `SET NX` with a TTL). The same `XACK` path succeeds only if the key was freshly set; replay delivers a no-op. This gives effectively-exactly-once semantics without requiring true exactly-once from the stream system.

## Consequences

### Benefits (Pros)

- **Zero new infrastructure.** Redis is already deployed for sessions and rate limiting. We can use a separate Redis instance (or a logical database) for streams to avoid resource contention — but the team's operational playbook, monitoring dashboards, and backup/restore procedures all transfer directly.
- **Fast delivery.** The first prototype — one stream, one consumer group, email-only — can be written, tested, and deployed in a single sprint.
- **Natural fit for WebSocket push.** Redis Pub/Sub, which the same `redis-py` client supports, is a well-known pattern for real-time push. Adding WebSocket notifications in Q2 will reuse the same infrastructure and the same `XADD` producer path; consumers will publish to a Pub/Sub channel that a WebSocket server subscribes to.
- **Consumer groups with explicit acknowledgment.** `XREADGROUP` + `XACK` gives us exactly the at-least-once delivery model we need. Pending Entry List (PEL) semantics mean unacknowledged messages are automatically tracked and can be claimed by other consumers if a worker crashes.
- **Message retention.** Streams can be trimmed to a fixed length (e.g., `MAXLEN ~ 100,000`) to bound memory while keeping recent messages available for reprocessing. This is sufficient for retry windows and operational debugging.
- **Negligible learning curve.** The team already uses `redis-py` for session operations. The API for streams (`XADD`, `XREADGROUP`, `XACK`, `XCLAIM`) is small and well-documented. The senior engineers can mentor the mid-level engineers in an afternoon.
- **Proven at our scale.** Redis Streams handle tens of thousands of messages per second in production at companies like Twitch, Deliveroo, and others. Our projected 5,000 msg/s peak is unremarkable for Redis.

### Costs (Cons)

- **No true exactly-once delivery.** Redis Streams, like nearly all message systems, provide at-least-once semantics natively. We must implement idempotent consumers with deduplication keys to achieve effectively-exactly-once for billing. This adds complexity to the billing consumer code and requires careful TTL sizing on dedup keys.
- **Single-node throughput ceiling.** Redis is single-threaded for command execution. While Redis Streams can handle ~100K msg/s on a modern instance, a single node is the bottleneck — no horizontal partitioning (unlike Kafka's per-partition parallelism). At 5,000 msg/s this is irrelevant; if we eventually outgrow it, we can shard by notification type across logical databases or separate Redis instances.
- **Memory-bound retention.** Kafka stores messages on disk with configurable retention by time or size; Redis Streams live in memory (backed by the same allocator as all Redis keys). Long-term archival of notification events requires a separate consumer that writes to PostgreSQL or S3. This is acceptable: we already need an audit-trail sink for billing compliance.
- **Consumer rebalancing is manual.** In Kafka, consumer group rebalancing is automatic when members join or leave. Redis Streams require the application to manage consumer registration and handle rebalancing on crash. The `redis-py` library provides the `xreadgroup` loop but leaves rebalancing to the developer. For a small worker pool (2–4 workers), we can implement a simple heartbeat-based takeover without a framework.
- **No built-in stream repartitioning.** Kafka allows repartitioning by changing the partition count (with caveats). Redis Streams are a single ordered sequence on a single key. Sharding requires application-level routing logic (e.g., stream key per notification type). We can adopt this later if needed.

## Alternatives Considered

### Apache Kafka

Kafka was seriously evaluated as an alternative. It offers:

- **True exactly-once semantics** via the transactional API and idempotent producers — no consumer-side deduplication work needed.
- **Disk-based retention** with configurable time/size limits, enabling long-term replay without secondary storage.
- **Automatic consumer rebalancing** when workers join or leave the consumer group.
- **Massive throughput** (millions of messages per second) with horizontal scaling via partitions.

**Why it was rejected:**

1. **Operational overhead is incompatible with team size.** A 6-person team with no infrastructure engineer would need to run and maintain a ZooKeeper or KRaft cluster. Even with managed services (Confluent Cloud, AWS MSK), the monthly cost at our modest budget is prohibitive, and the cloud-specific API surfaces add learning time. Self-hosted Kafka requires dedicated expertise in JVM tuning, partition sizing, ISR configuration, disk I/O planning, and monitoring — expertise we do not have and cannot acquire in two weeks.

2. **Time-to-value exceeds the constraint.** Setting up Kafka, designing topic and partition strategies, writing producers and consumers, and training the team would take 4–6 weeks before production use. The constraint explicitly limits setup/migration to 2 weeks.

3. **Overprovisioned for the workload.** At 500–5,000 messages per second, Kafka's horizontal scaling and million-msg/s throughput are unused capacity. We would pay an operational and cognitive tax for features that Redis Streams already deliver at our scale.

4. **No Redis reuse.** Adding Kafka introduces a second data-infrastructure system (Java process, new monitoring, new backup strategy) alongside Redis. Every operational procedure — restart, backup, failover — must now be documented and practiced for two systems instead of one.

### PostgreSQL Listen/Notify + job table

We also considered using PostgreSQL's `LISTEN/NOTIFY` with a job table and a scheduler (pg_cron or application-level polling). This would keep the stack purely Postgres.

**Why it was rejected:**

- `LISTEN/NOTIFY` has a hard payload limit (~8,000 bytes) and no built-in acknowledgment or consumer group semantics.
- Message delivery is not durable — if the listening connection drops, notifications are lost.
- Polling a job table introduces write contention on the `notifications` table at our scale, competing with the primary transactional workload.
- No built-in retry or dead-letter queue — all of this must be built from scratch, which negates the "simplicity" argument.

## Summary

Redis Streams let us decouple notifications from the request cycle in one sprint, reusing existing infrastructure and team knowledge. The trade-offs — consumer-side idempotency for exactly-once, manual rebalancing, memory-bound retention — are well-understood and straightforward to mitigate at our scale. Apache Kafka is the stronger system at planetary scale but imposes an operational cost that a 6-person team cannot sustainably carry for a workload Redis handles comfortably.
