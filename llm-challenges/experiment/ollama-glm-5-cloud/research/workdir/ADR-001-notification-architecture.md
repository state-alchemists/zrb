# ADR-001: Notification Subsystem Architecture

## Status

Proposed

## Context

Our SaaS project management platform handles notifications (emails, webhooks) synchronously within HTTP requests, causing request timeouts, silent failures, cascading outages, and no delivery guarantees for billing-critical events. We need to decouple notification processing from the request cycle.

**Current scale:** 85K MAU, ~2M tasks/month, peak 500 req/s.  
**Target scale:** 10x traffic growth without re-architecting.

**Business requirements:**
- Async processing to unblock HTTP responses
- Retry with exponential backoff for transient failures
- At-least-once delivery for all notifications; exactly-once semantics for billing events
- Dead-letter queue for unrecoverable failures
- Foundation for WebSocket push notifications within 2 quarters

**Team constraints:**
- 6 engineers (3 senior, 3 mid-level), no dedicated infrastructure engineer
- Redis already in production for sessions/rate limiting
- No Kafka operational experience
- Must deliver value within 2 weeks of setup/migration
- Modest budget — managed Confluent Cloud at scale is cost-prohibitive

## Decision

**We will use Redis Streams** as the initial message backbone for the notification subsystem.

Redis Streams provides sufficient throughput, ordering guarantees, and consumer group semantics for our current and projected scale, with minimal operational overhead given our existing Redis deployment and team expertise.

## Consequences

### Pros

1. **Fast time-to-value.** Redis is already operational. Adding Streams requires enabling the module (if not present) and creating stream consumers — achievable within the 2-week constraint. No new infrastructure to provision, secure, or monitor.

2. **Team velocity.** Engineers know Redis. The learning curve for `XADD`, `XREADGROUP`, `XACK` is shallow compared to Kafka's partition assignment, offset management, and broker coordination concepts.

3. **Cost efficiency.** No new licensing or managed service costs. Redis memory usage for streams is predictable and bounded via `MAXLEN` or time-based trimming.

4. **Sufficient throughput.** Redis Streams handles 100K–500K messages/second on modest hardware. Our peak of 500 req/s with 1–3 notifications per event is 1.5K–3K msg/s — well under capacity, with headroom for 10x growth.

5. **Consumer groups.** `XREADGROUP` provides blocking reads, load distribution across consumers, and automatic message tracking via `XPENDING`. Retry is built-in via unacknowledged message reprocessing.

6. **Ordered delivery.** Per-stream ordering guarantee ensures notifications for a given entity (task, project) are processed in sequence, preventing race conditions in webhook delivery.

### Cons

1. **No native exactly-once semantics.** Redis Streams provides at-least-once delivery. We must implement idempotent consumers that deduplicate by message ID, using PostgreSQL as the authoritative source for billing notification state. This is additional application logic but tractable for 6 engineers.

2. **Memory-bound retention.** Unlike Kafka's disk-based retention, Redis Streams are memory-resident. Long retention requires more RAM. We'll cap stream length via `MAXLEN ~ 100000` and persist critical events to PostgreSQL for replay capability.

3. **Limited replay granularity.** Kafka offers per-message timestamp seeking. Redis Streams replay requires manual tracking via XIDs. For our use case (recent notifications, not months-long audit trails), this is acceptable.

4. **Operational risk on single Redis instance.** If Redis fails, the notification queue is unavailable. Mitigation: Redis Sentinel or Redis Cluster for HA (future hardening); immediate path is accepting brief queue unavailability with PostgreSQL outbox fallback.

5. **Less mature ecosystem.** Fewer tooling options compared to Kafka (no native equivalents to Kafka Connect, Schema Registry). We implement webhook delivery and retry logic in Python using `redis-py`.

## Alternatives Considered

### Apache Kafka

**Why rejected:**

1. **Operational overhead exceeds team capacity.** Kafka requires broker clusters, ZooKeeper (or KRaft), and specialized monitoring. With no dedicated infrastructure engineer and zero Kafka experience, we risk a fragile deployment that the team cannot debug under pressure.

2. **Time-to-value violation.** Setting up a production-grade Kafka cluster, establishing operational runbooks, and training the team would exceed the 2-week constraint. We'd deliver value later while accepting risk longer.

3. **Cost at target scale.** Self-hosted Kafka on AWS requires 3+ brokers for quorum, plus monitoring infrastructure. Managed Confluent Cloud at 10x traffic (1.5M+ notifications/month) would strain the modest budget.

4. **Over-engineering for current needs.** Kafka's strengths—multi-consumer topologies, long-term log retention, exactly-once transactions across partitions—are not aligned with our immediate problem (decoupling notifications from HTTP). We can achieve our goals with simpler tooling.

5. **Migration friction.** The monolith has no existing message infrastructure. Introducing Kafka requires more code changes (producer clients, consumer framework, offset management) than Redis Streams integration via existing `redis-py` usage.

**When to reconsider:** If traffic exceeds Redis cluster capacity (>100K msg/s sustained), or we need cross-region event replication, or the team gains Kafka operational expertise, migrate to Kafka for its superior durability and ecosystem. This is unlikely at 10x our current scale (15K–30K msg/s). The outbox pattern in PostgreSQL provides migration flexibility—we retain control of notification state.

---

**Implementation notes (not part of ADR, but for context):**

- Stream naming: `notifications:{type}:{priority}` (e.g., `notifications:webhook:high`, `notifications:email:normal`)
- Consumer group: `notification-workers`
- Delivery loop: `XREADGROUP` → process → `XACK` on success; `XPENDING` for retry backlog
- Dead-letter: failed after N retries → `notifications:dlq` stream
- Exactly-once for billing: persist notification ID in PostgreSQL, consumer checks existence before processing