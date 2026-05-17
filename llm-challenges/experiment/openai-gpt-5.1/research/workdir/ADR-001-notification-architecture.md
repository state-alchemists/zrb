# Title

Async Notification Subsystem Architecture: Kafka vs Redis Streams

# Status

Proposed

# Context

Our SaaS project management platform currently handles notifications (emails, webhooks, and future WebSocket pushes) synchronously inside the HTTP request cycle of a Python/Flask monolith backed by PostgreSQL and Redis. With ~85,000 monthly active users, ~2M tasks per month, and peak traffic of ~500 req/s, synchronous notification delivery has led to high request latency (average ~800ms, spikes to ~8s), silent delivery failures when downstream providers are unavailable, and cascading failures when slow webhooks exhaust connection pools.

We need a notification subsystem that:
- Decouples notification processing from the HTTP request cycle using asynchronous processing.
- Supports retries with exponential backoff and dead-letter handling for failed deliveries.
- Provides at-least-once delivery guarantees for all billing-related events, and exactly-once semantics where feasible.
- Can support real-time WebSocket push notifications within two quarters.
- Can handle at least 10x traffic growth without requiring a major re-architecture.

Operational constraints:
- Engineering team of 6 (3 senior, 3 mid), no dedicated infrastructure engineer.
- Redis is already in production (sessions, rate limiting); Kafka is not currently used and no one has Kafka experience.
- We must deliver initial value (offloading notifications out of the request cycle with retries and basic guarantees) within ~2 weeks of engineering effort.
- Budget is modest; we cannot rely on high-cost fully managed Kafka offerings like Confluent Cloud at projected scale.
- We must maintain exactly-once semantics for billing notifications (e.g., "trial expired", "payment failed").

Within this context, we are evaluating two options for the core notification queue/bus: Apache Kafka and Redis Streams.

# Decision

We will build the notification subsystem on top of Redis Streams (XADD/XREADGROUP consumer groups), using our existing Redis cluster, and implement application-level idempotency and deduplication to achieve at-least-once delivery for all notifications and effective exactly-once semantics for billing notifications.

Redis Streams is preferred over Apache Kafka because, given our current scale, team experience, timelines, and budget, it provides sufficient throughput and ordering guarantees with significantly lower operational complexity and faster time-to-value. While Kafka offers stronger built-in guarantees and scalability for very high throughput event streaming, adopting and operating Kafka (either self-managed or via a cost-effective managed offering) would exceed our two-week setup constraint, add meaningful operational risk for a small team without Kafka expertise, and is disproportionate to our current and near-term traffic profile.

# Consequences

## Pros

1. Lower operational complexity and faster delivery
   - We already run Redis in production; extending it with Streams reuses existing operational knowledge, monitoring, and infrastructure.
   - No need to introduce ZooKeeper/KRaft clusters, brokers, schema registries, or new networking/security concerns required by Kafka.
   - We can implement a minimal but robust async notification pipeline (producer + worker consumers + retry queues + DLQ) well within the two-week constraint.

2. Adequate throughput and ordering for current and 10x projected scale
   - Our current notification volume (derived from ~500 req/s peak and ~2M tasks/month) is well within Redis Streams throughput capabilities on a modest AWS instance.
   - Redis Streams supports ordered append-only logs per stream and delivery via consumer groups, which are sufficient to maintain ordering per logical key (e.g., per user or per billing account) by key-partitioning into streams.
   - A single Redis node can typically handle hundreds of thousands to millions of ops/sec in practice; even a 10x growth from current traffic is unlikely to saturate Streams if we design the data model and consumers sensibly.

3. Delivery guarantees via stream semantics + application idempotency
   - Redis Streams with consumer groups provide at-least-once delivery semantics: messages are acknowledged explicitly via XACK only after successful processing.
   - Pending entry lists allow us to detect stuck/unacked messages and implement retries with exponential backoff and dead-letter routing (e.g., via additional streams such as `notifications.retry` and `notifications.dlq`).
   - Exactly-once semantics for billing notifications can be implemented by combining at-least-once delivery with idempotent consumers using PostgreSQL/Redis idempotency keys, transactional updates, and side-effect tracking (e.g., store a `billing_notification_id` and only act once).

4. Simpler path to WebSocket push notifications
   - The same Streams-based pipeline can feed WebSocket workers that push real-time updates; web and mobile clients can subscribe to user- or project-specific channels fed by notification events read from Streams.
   - No need to introduce a separate streaming or pub/sub layer beyond Redis.

5. Cost-effective and incremental
   - We avoid the fixed and operational costs of running a Kafka cluster (minimum 3 brokers, plus ZooKeeper/KRaft) or paying for high-end managed Kafka.
   - We can start on our existing Redis deployment and later scale vertically or move to Redis Cluster/managed Redis if needed.

## Cons

1. Weaker built-in streaming guarantees and tooling vs Kafka
   - Redis Streams lacks some advanced features of Kafka such as log compaction, long-term high-volume retention at low cost (disk-optimized), and rich ecosystem (Kafka Connect, ksqlDB, schema registry).
   - Exactly-once processing is not natively supported; we must implement idempotency and deduplication at the application level and be careful with transactional boundaries around side effects (emails, webhooks, billing changes).

2. Retention and storage trade-offs
   - Redis is memory-first; while Streams can be configured with capped length and eviction policies, long-term retention of large volumes of notification events may be more expensive than Kafka’s disk-based model.
   - To keep memory usage under control, we will likely need to trim older messages aggressively or archive to cold storage, which complicates use cases that expect very long-lived event logs.

3. Limited horizontal scalability compared to Kafka’s partition model
   - Kafka is designed to scale linearly by partitioning topics and adding brokers; Redis Cluster scaling and key/stream sharding are more manual and less seamless for very high-throughput or multi-region scenarios.
   - If we significantly exceed projected 10x traffic growth or expand into complex streaming analytics, we may need to revisit the choice and migrate to Kafka or another event streaming platform.

4. Operational risk around single point of failure if not properly configured
   - Today we use a single primary Redis with a replica; for notifications, we must ensure robust high availability (HA) and persistence configuration (AOF/RDB) to avoid message loss during failover.
   - Misconfiguration (e.g., aggressive eviction, insufficient memory, improper persistence) could degrade notification reliability.

# Alternatives Considered

## Apache Kafka

Kafka is a distributed commit log and event streaming platform with strong ordering and durability guarantees, consumer groups, high throughput, and sophisticated retention and processing semantics. It is widely used for large-scale event-driven architectures.

We are not choosing Kafka at this time for the notification subsystem for the following reasons:

1. Operational complexity and team experience
   - Kafka requires operating and monitoring a multi-broker cluster plus ZooKeeper or KRaft controllers, with careful tuning of partitions, replication, storage, and networking.
   - Our team has no prior Kafka experience and no dedicated infrastructure engineer; realistically, the learning curve and setup time (including CI/CD, metrics, alerting, backup, and security) would exceed the two-week delivery requirement and introduce avoidable reliability risk.

2. Overprovisioned for current and near-term scale
   - Our current peak of ~500 req/s and projected 10x growth are well within Redis Streams’ capabilities; Kafka’s strengths around millions of messages per second and huge topic partitions are not strictly necessary yet.
   - We do not currently need long-term analytical retention or cross-service event-sourcing capabilities that would fully leverage Kafka’s design.

3. Cost and infrastructure footprint
   - Running a production-grade Kafka cluster on AWS (self-managed) would require dedicated instances, storage, and operational overhead beyond our modest budget.
   - Fully managed Kafka offerings (e.g., Confluent Cloud) that significantly reduce operational burden would, at the scale required for 10x growth and high availability, be cost-prohibitive per our constraints.

4. Exactly-once semantics vs implementation effort
   - Kafka supports transactional producers and exactly-once processing semantics when combined with idempotent producers and transactional consumers. However, designing and implementing a correct exactly-once billing notification pipeline around Kafka would still require non-trivial engineering and operational work.
   - Given our lack of Kafka expertise, relying on its advanced transactional semantics safely in production within a two-week window is unrealistic, whereas implementing idempotent consumers on top of Redis Streams and PostgreSQL is better aligned with existing team skills.

5. Additional moving parts for WebSocket push notifications
   - Kafka does not directly solve WebSocket fan-out; we would still need a separate component (e.g., a WebSocket gateway) that consumes from Kafka topics and pushes to clients, plus potentially another fast cache/pub-sub layer (often Redis) for in-app real-time messaging.
   - Since we already operate Redis, using it directly for both the notification queue and WebSocket fan-out reduces system complexity.

In summary, while Kafka is the stronger choice for very high throughput, large-scale event streaming with long-term retention and advanced processing, its operational complexity, cost, and our team’s lack of experience make it a poor fit for our current constraints and timelines. Redis Streams provides a simpler, cheaper, and sufficiently capable foundation for our notification subsystem, with the understanding that we may revisit Kafka or another event streaming platform if our scale or requirements evolve beyond what Redis can comfortably support.
