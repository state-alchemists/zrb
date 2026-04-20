# ADR-001: Notification Subsystem Architecture

## Status

Proposed

## Context

Our SaaS project management platform (85K MAU, ~2M tasks/month, peak 500 req/s) handles notifications synchronously within HTTP requests. This has caused request timeouts (800ms avg, 8s spikes), silent failures with no retry mechanism, and cascading failures when webhook endpoints are slow.

We need to:
- Decouple notification delivery from the HTTP request cycle
- Implement retry with exponential backoff
- Guarantee at-least-once delivery for all events, exactly-once for billing-critical notifications
- Support WebSocket push notifications within 2 quarters
- Scale to 10x current traffic without re-architecting

**Key Constraints:**
- Team: 6 engineers (no dedicated infrastructure engineer)
- Already running Redis in production (sessions, rate limiting)
- No Kafka experience on the team
- Maximum 2 weeks to deliver initial value
- Modest budget (managed Kafka services like Confluent Cloud not viable at scale)
- Exactly-once semantics required for billing notifications

## Decision

**We will use Redis Streams** as the message broker for the notification subsystem.

### Justification

Redis Streams meets our requirements while respecting our constraints:

1. **Infrastructure fit**: We already operate Redis in production. Adding streams requires no new servers, no new monitoring stacks, and no new operational runbooks. The team has existing Redis operational knowledge.

2. **Time to value**: Engineers can implement a working async notification system within the 2-week window using familiar tooling. Python clients (`redis-py`) are mature and well-documented.

3. **Throughput sufficiency**: Redis Streams handles 100K-1M messages/second on modest hardware—well above our 10x scaling target (5,000 req/s peak). Our notification volume (~50-100 notifications/sec estimated) is trivially within capacity.

4. **Consumer groups**: Redis Streams supports consumer groups natively via `XREADGROUP` and `XACK`, enabling parallel processing across multiple workers with automatic load distribution and message acknowledgment.

5. **Message ordering**: Per-stream ordering guarantees ensure notifications for a given entity (e.g., task updates) are processed in sequence when needed.

6. **Message retention**: Configurable via `MAXLEN` or time-based eviction. For notifications, we only need retention until confirmed delivery—minutes to hours, not days.

7. **Exactly-once via application idempotency**: While Redis Streams provides at-least-once delivery, we will implement idempotency at the application layer for billing notifications using:
   - Unique idempotency keys stored with each notification
   - Postgres `INSERT ... ON CONFLICT DO NOTHING` at the notification processing layer
   - Duplicate detection before sending to external providers (email, webhook, payment gateway)

   This pattern is standard practice and avoids the operational complexity of Kafka's transactional semantics while still achieving the business requirement.

## Consequences

### Pros

- **Fast implementation**: 2-week delivery achievable; no new infrastructure to provision
- **Lower operational burden**: Single system to monitor; no Kafka clusters to manage, rebalance, or debug
- **Cost-effective**: No additional licensing or managed service fees
- **Team familiarity**: Existing Redis expertise reduces learning curve
- **Adequate scale**: Handles 10x growth with headroom; can revisit if we exceed 100x
- **Simpler stack**: One fewer moving part in the architecture

### Cons

- **No native exactly-once**: Must implement idempotency at application layer for billing notifications. This adds code complexity but is a well-understood pattern.
- **Limited long-term retention**: Redis Streams is not designed for multi-day or multi-week retention. If we later need to replay historical notifications (e.g., for audit or analytics), we would need a separate solution.
- **Single point of failure**: Redis is already a SPOF for sessions; now also for notifications. Mitigation: Redis Sentinel or clustering for HA (worth considering as overall Redis dependency grows).
- **Less ecosystem tooling**: Kafka has richer ecosystem (Kafka Connect, Schema Registry, ksqlDB). We accept this tradeoff for simplicity.
- **Future migration risk**: If we eventually need Kafka-scale throughput (millions/sec) or multi-datacenter replication, migrating off Redis Streams would require rework.

## Alternatives Considered

### Apache Kafka

**Why rejected:**

| Factor | Assessment |
|--------|------------|
| Operational complexity | High. Requires provisioning Zookeeper (or KRaft-mode Kafka 3.x), broker clusters, monitoring, and operational expertise our team lacks. Estimated 4-6 weeks to production-ready. |
| Team experience | None. Steep learning curve for concepts: partitions, offsets, consumer groups, rebalancing, log compaction. |
| Budget | Self-hosted Kafka requires dedicated infrastructure. Managed Confluent Cloud exceeds our budget at scale. |
| Exactly-once semantics | Native support is compelling, but our billing notification volume (~1% of total) doesn't justify the infrastructure cost for this alone. Application-level idempotency is sufficient. |
| Throughput | Overkill for our needs. Kafka excels at millions of messages/sec; we need hundreds. |
| Retention | Long-term retention is a strength, but notifications don't require it. We delete after confirmed delivery. |

Kafka is the right choice for organizations with dedicated infrastructure teams, high-volume event streaming needs, or regulatory requirements for audit trails. Our use case is simpler, and the constraints (team size, time, budget, existing stack) favor Redis Streams.

**When to reconsider**: If we grow beyond 10M tasks/month, require multi-region replication, or need to build an event-sourced audit system, Kafka would become the appropriate choice. That decision can be made when those requirements materialize—not preemptively.