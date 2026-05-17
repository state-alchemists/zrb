# ADR-001: Notification Subsystem Architecture

## Status

Proposed

## Context

The notifications module in our Python/Flask monolith synchronously sends emails and webhooks inside the HTTP request cycle. At 85,000 MAU and peak loads of ~500 req/s, this has produced:

- **Request timeouts**: Average notification latency of 800ms, spiking to 8s during peak hours.
- **Silent failures**: No retry mechanism; dropped notifications when downstream providers are unavailable.
- **Cascading failures**: Slow webhook endpoints caused connection pool exhaustion, impacting unrelated features.
- **No delivery guarantees**: Billing-critical notifications (e.g., "trial expired", "payment failed") must be delivered exactly once, but the current system provides no such guarantee.

We need to decouple notification processing from the request cycle, support retry with exponential backoff, and guarantee at-least-once delivery (with exactly-once for billing events). We must also support real-time WebSocket push within two quarters and handle 10x traffic growth without re-architecting.

Our constraints are tight:
- Engineering team of 6 (3 senior, 3 mid-level), with **no dedicated infrastructure engineer**.
- We already operate Redis (ElastiCache or self-hosted) for session storage and rate limiting.
- **No team member has production Kafka experience**.
- The solution must be operational and delivering value within **2 weeks**.
- Budget is modest; we cannot afford managed Confluent Cloud at scale today.

## Decision

We will adopt **Redis Streams** as the backbone of the notification subsystem.

### Justification

**1. Operational fit and speed to value**
We already run Redis in production. Adding Streams requires no new deployment paradigm, no new operational runbooks, and no additional vendor. A mid-level engineer can integrate `XADD` / `XREADGROUP` into our Flask application and have a working consumer group deployed within days, well inside the 2-week deadline. By contrast, self-hosting Kafka (broker provisioning, replication factor planning, partition sizing, KRaft or ZooKeeper management, consumer group rebalancing tuning) realistically requires several weeks of setup and ongoing operational attention that our team cannot provide.

**2. Sufficient throughput and headroom for growth**
Redis Streams on a single, appropriately sized instance can sustain tens of thousands of operations per second. Our current peak of ~500 req/s, and even our 10x growth target (~5,000 req/s), sit comfortably within the performance envelope of a single Redis node. Kafka's horizontal scalability and partition model are powerful, but they are unnecessary overhead at this scale.

**3. Consumer groups and decoupled processing**
Redis Streams provides native consumer groups (`XGROUP CREATE`, `XREADGROUP`, `XACK`) that allow us to fan out messages to independent consumers: one for email, one for webhooks, and a future one for WebSocket push. Pending entries (`XPENDING`) and claim (`XCLAIM`) enable us to build retry with exponential backoff by re-assigning unacknowledged messages to a redelivery sweeper process. This directly satisfies our requirement to decouple work and retry failed deliveries.

**4. Exactly-once semantics for billing events via idempotent consumers**
Redis Streams does not provide broker-level exactly-once semantics comparable to Kafka Transactions. We will instead implement **exactly-once processing** at the application layer, a pattern well-suited to our Flask/PostgreSQL stack:
- The producer generates a unique idempotency key (UUID) per billing notification and includes it in the stream message.
- The consumer inserts a processed record into a PostgreSQL table with a unique constraint on the idempotency key.
- If the consumer crashes and the message is redelivered, the duplicate write fails the unique constraint, and the consumer safely acknowledges the message.

This idempotent-consumer pattern is simpler to operate and debug than Kafka's exactly-once producer/transactional consumer APIs, which require careful handling of `transactional.id`, `isolation.level`, and consumer group fencing—expertise we do not currently have on the team.

**5. Cost control**
Because we already run Redis, the marginal infrastructure cost is near zero. We may provision a separate Redis instance for Streams to isolate noisy-neighbor effects from session storage, but this is still a modest single-node deployment. Managed or self-hosted Kafka, on the other hand, would require either a multi-broker cluster or a paid managed service, both of which conflict with our modest budget.

## Consequences

### Pros

- **Fast migration**: We can move the highest-impact notification types (billing events) off the synchronous path within days.
- **Low operational burden**: Existing Redis operational expertise (monitoring, failover, backup) transfers directly to Streams.
- **Minimal cost**: No new licensing or managed-service fees; marginal hardware cost is small.
- **Straightforward retry mechanics**: `XPENDING` + `XCLAIM` give us visibility into stuck messages and a clean path to redelivery.
- **Future-proof for WebSockets**: Redis Streams and Pub/Sub can coexist, allowing us to fan out real-time events to WebSocket servers without introducing a third messaging system.

### Cons

- **No native exactly-once broker semantics**: We must implement deduplication in application code (PostgreSQL idempotency table). If implemented incorrectly, billing events risk double-processing during consumer crashes.
- **Memory-bound retention**: Message retention is governed by memory (or AOF disk size) and explicit `MAXLEN` trimming. If we misconfigure trimming or AOF persistence, we could lose messages under a disk-space or memory-pressure event. We will mitigate this with a conservative `MAXLEN` policy and nightly archive of processed billing events to PostgreSQL.
- **Consumer-group rebalancing is simpler and less robust than Kafka's**: Redis does not offer the same partition-assignment guarantees during consumer membership changes. Rapid consumer scaling events could cause temporary message duplication until consumers stabilize. Given our predictable traffic and planned gradual scaling, this is acceptable.
- **Single-node bottleneck risk**: While a single Redis node handles our 10x target, growth beyond that (e.g., 50x–100x) or large message payloads could force a future migration to a horizontally scalable log system. We accept this as a deliberate trade-off: optimize for today's constraints, with a known re-evaluation point at ~50,000 req/s sustained.

## Alternatives Considered

### Apache Kafka

**Why it was considered:**
Kafka is the industry-standard distributed log. It offers durable, log-based persistence, mature consumer groups with automatic partition rebalancing, and native exactly-once semantics via idempotent producers and transactional consumers. It is designed to scale horizontally to millions of messages per second.

**Why it was rejected:**
1. **Operational complexity exceeds team capacity.** Running a production Kafka cluster (even KRaft mode) requires expertise in broker tuning, replication factor management, partition assignment, and consumer group fencing. Our team has zero Kafka experience and no infrastructure engineer to own this.
2. **2-week deadline is unrealistic.** A safe Kafka deployment—including cluster provisioning, monitoring, alert thresholds, and consumer testing—cannot be completed and battle-tested by a six-person feature team in two weeks.
3. **Budget constraints.** Managed options such as Confluent Cloud or AWS MSK are ruled out by our modest budget. Self-hosting to save money incurs the operational costs described above.
4. **Overkill for current and near-term scale.** At ~500 req/s peak, Kafka's architectural advantages (partition-level parallelism, massive horizontal scale) provide no practical benefit. The complexity is pure overhead until we reach sustained throughput orders of magnitude higher than today's volumes.

While Kafka is the technically "pure" choice for a high-scale log architecture, it violates our primary constraints of time, budget, and operational bandwidth. Redis Streams provides the message-persistence, consumer-group, and retry semantics we need today, at a complexity level our team can operate safely.
