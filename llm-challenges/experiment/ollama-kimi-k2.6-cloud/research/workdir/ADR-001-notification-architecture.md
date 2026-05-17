# ADR-001: Notification Architecture

- **Status**: Proposed

## Context

Our SaaS project management platform serves 85,000 monthly active users and creates roughly 2M tasks per month. During business hours we see peak traffic of ~500 req/s. Today, notifications (emails and webhooks) are sent synchronously inside the HTTP request cycle. This has produced four concrete problems:

1. **Request timeouts**: Average notification latency is 800ms and spikes to 8s during peak hours because workers wait for SMTP and HTTP round-trips before returning a response to the user.
2. **Silent failures**: If a remote email provider or webhook endpoint is down, the notification is dropped. We have no retry logic and no dead-letter queue.
3. **Cascading failures**: Two incidents this year involved a slow webhook endpoint exhausting our connection pool and degrading unrelated features.
4. **Missing delivery guarantees**: Billing-critical notifications (e.g., "trial expired", "payment failed") must be delivered exactly once, yet the current system provides no idempotency or audit trail.

We must decouple notification dispatch from the request cycle, add retry with exponential backoff, support at-least-once delivery for all events and exactly-once for billing events, and lay the groundwork for real-time WebSocket pushes within two quarters. We also need a 10x traffic growth path (peak ~5,000 req/s) without re-architecting.

Key constraints:

- Engineering team of 6 (3 senior, 3 mid-level), with no dedicated infrastructure engineer.
- We already run Redis in production for session storage and rate limiting.
- No Kafka experience on the team.
- Migration and setup must not exceed two weeks before delivering value.
- Budget is modest; we cannot afford managed Confluent Cloud at scale.

## Decision

> We will use Redis Streams as the messaging backbone for the notification subsystem.

This choice is driven by the fact that our throughput requirements (current 500 req/s, target 5,000 req/s) are well within the operational envelope of a single Redis instance, while the team’s lack of Kafka experience and the two-week time-to-value mandate make introducing a new distributed log broker high-risk and low-return at this stage. Redis Streams gives us ordered, durable async dispatch with consumer groups and explicit acknowledgement, all on infrastructure we already operate and monitor.

## Consequences

### Pros

1. **Low operational burden**: We reuse an existing Redis node that already supports sessions and rate limiting. There is no new JVM to tune, no ZooKeeper/KRaft ensemble to manage, and no partition topology to design.
2. **Fast migration**: The Python Redis client (`redis-py`) natively supports `XADD`, `XREADGROUP`, `XACK`, and `XCLAIM`. We can move the first notification types async within days, satisfying the two-week deadline.
3. **Zero incremental infrastructure cost**: No extra AWS instances or managed-service fees are required.
4. **Built-in retry and recovery**: Consumer groups maintain a Pending Entry List (PEL) for each member. Failed or timed-out messages remain pending and can be reclaimed by another worker with `XCLAIM` after an idle threshold. This gives us exponential-backoff retry and dead-letter behavior without external cron jobs or delayed-queue libraries.
5. **Ordering guarantees**: Redis Streams assigns monotonically increasing IDs, providing total ordering of events within a stream. This satisfies our requirement to process task-level and user-level notifications in the sequence they occurred.
6. **Path to WebSocket push**: The planned real-time WebSocket layer can use Redis Pub/Sub on the same node, avoiding the operational overhead of a second broker.
7. **Ample throughput headroom**: A single Redis instance handles >100,000 operations/second, so our 10x target of ~5,000 req/s leaves significant margin without clustering.

### Cons

1. **Memory-bound retention**: Streams are kept in RAM. Without an explicit cap (`MAXLEN`) or aggressive trimming, backlog growth could exhaust memory. Mitigation: trim acknowledged events aggressively; at our volume (~2M small JSON events/month) a 48-hour retention window consumes a trivial amount of memory.
2. **Durability model**: Redis AOF/RDB provides good durability but is not a strict write-ahead log. A catastrophic node failure could lose unacknowledged messages that have not yet been flushed. Mitigation: run AOF with `appendfsync everysec` and schedule snapshots during low-traffic windows.
3. **Application-level exactly-once burden**: Redis Streams does not offer transactional exactly-once semantics to external systems. We must implement an idempotency table in PostgreSQL (already in use) keyed by a unique event identifier, and check that table before dispatching billing emails or webhooks. The same burden would exist with Kafka for external HTTP calls, but with Redis the primitive is explicitly absent, so the requirement is more visible.
4. **Harder cross-topic joins**: If future analytics or audit features require joining multiple event streams, Redis Streams offers no query semantics beyond linear reads. This is acceptable for a notification pipeline today but may become a limitation if stream-processing logic grows complex.
5. **Scaling ceiling**: While 10x growth fits comfortably in a single Redis instance, sustained growth beyond ~20–50k messages/second or multi-day backlogs would force a re-architecture to a disk-centric log broker. We accept this as a future trigger rather than a present cost.

## Alternatives Considered

### Apache Kafka
**Rejected.** Kafka is the stronger pure-technology choice at hyperscale — it offers disk-based retention, high horizontal throughput, and transactional exactly-once semantics between Kafka topics — but the operational complexity is disproportionate to our current needs and constraints.

- Self-hosted Kafka requires broker clusters, topic and partition planning, consumer group rebalancing tuning, and dedicated monitoring. Our six-person team has zero Kafka experience and no infrastructure engineer to own on-call rotations for a distributed log.
- Kafka’s transactional exactly-once does not extend to external email and webhook APIs, which are uncoordinated participants. Exactly-once delivery to those endpoints still requires an application-level idempotency layer, meaning Kafka does not remove the PostgreSQL idempotency requirement we must build anyway.
- Managed Confluent Cloud is excluded by our modest budget.
- The two-week migration window would likely be consumed entirely by cluster provisioning and client hardening, delaying value delivery.

We would reconsider Kafka only if our single-node Redis headroom were exhausted or if we needed complex multi-topic stream processing (e.g., joins, windowed aggregations) that Redis cannot support.
