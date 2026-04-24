# Title

Notification Subsystem Architecture: Kafka vs Redis Streams

# Status

Proposed

# Context

Our SaaS project management platform currently handles notifications (emails and webhooks) synchronously inside the HTTP request cycle of a Python/Flask monolith. With ~85,000 MAUs, ~2M tasks/month, and peak load around 500 req/s, synchronous notification delivery has led to:

- High latency (average ~800ms, spikes up to 8s) due to waiting on external email/webhook providers.
- Silent failures when downstream providers are unavailable (no retry mechanism, no dead-letter queue).
- Cascading failures, where slow webhook endpoints exhaust connection pools and impact unrelated features.
- No delivery guarantees, despite a requirement for at-least-once (and ideally exactly-once) delivery for billing-critical notifications (e.g., "trial expired", "payment failed").

We need to decouple notification processing from the HTTP request lifecycle via an asynchronous subsystem that:

- Provides durable messaging with backpressure and buffering.
- Supports retry with exponential backoff and dead-letter queues.
- Guarantees at-least-once delivery, and supports exactly-once semantics for billing notifications where feasible.
- Can support additional real-time WebSocket push notifications within two quarters.
- Can handle at least a 10x increase in traffic without a fundamental re-architecture.

Constraints:

- Small engineering team (6 engineers; 3 senior, 3 mid-level), no dedicated infrastructure engineer.
- Redis is already in production, used for session storage and rate limiting.
- No existing Kafka experience on the team.
- Initial rollout must deliver value within ~2 weeks of engineering work.
- Budget is modest; managed Kafka offerings like Confluent Cloud at full production scale are not currently affordable.
- We must maintain exactly-once semantics for billing notifications end-to-end (e.g., avoid double-charging, duplicate invoices or missing billing emails).

Within this context, we are evaluating two options for the notification subsystem message backbone:

1. Apache Kafka
2. Redis Streams

# Decision

We choose **Redis Streams** as the primary messaging backbone for the notification subsystem.

This choice is driven by the combination of our moderate scale, stringent delivery guarantees for a narrow class of billing events, tight implementation timeline, existing operational familiarity with Redis, and lack of Kafka expertise on the team. Redis Streams provides ordered, durable append-only logs per stream, consumer groups with at-least-once delivery semantics, and persistence via AOF/RDB, which are sufficient to meet our notification throughput and reliability requirements with significantly lower operational and cognitive overhead than operating Kafka ourselves.

Kafka provides stronger guarantees and richer semantics for large-scale streaming workloads (e.g., high partitioned throughput, long-term retention, exactly-once processing across partitions with transactions), but those advantages are not strictly necessary at our projected traffic levels and come with substantial operational complexity at our team size and budget.

We will design the notification subsystem so that the message abstraction is decoupled from Redis-specific APIs (e.g., via an internal `NotifierQueue` interface). This will leave open the possibility of migrating to Kafka or a managed streaming platform in the future if scale or requirements significantly increase.

# Consequences

## Pros

1. **Lower operational complexity (fits current team)**
   - We already run and operate Redis in production; extending its use to Redis Streams adds incremental complexity rather than introducing a new distributed system.
   - No need to run and tune Zookeeper/Kafka brokers, manage partitions, ISR, or coordinate rolling upgrades and storage planning.
   - Simpler local development and testing environment—developers can run a single Redis instance or use in-memory variants.

2. **Meets current and 10x projected throughput needs**
   - With current peak ~500 req/s and an estimated notification fan-out of a few messages per request, expected peak notification message throughput is in the low thousands of messages per second.
   - A modest Redis cluster (or even a single primary with replica) with Streams can comfortably handle tens of thousands of operations per second when sized and configured correctly, leaving ample headroom for a 10x increase without re-architecting.

3. **Ordering and consumer groups suitable for notifications**
   - Redis Streams preserve message order within a stream; by modeling a stream per notification type or per tenant, we can keep ordering semantics where needed (e.g., billing events per account).
   - Consumer groups provide at-least-once delivery with mechanisms to claim pending messages and to track acknowledgements, suitable for worker-based notification processing.

4. **Supports retries, backpressure, and dead-letter patterns**
   - We can implement retry with exponential backoff by re-enqueuing messages with delayed processing (e.g., using sorted sets or dedicated "retry" streams) and moving failed messages to a dead-letter stream after max attempts.
   - Visibility over pending/failed messages via XREADGROUP and XPENDING enables monitoring of stuck or slow consumers.

5. **Faster time-to-value**
   - Implementation can leverage existing Redis client libraries and infrastructure, making a 2-week initial rollout achievable.
   - The learning curve for Redis Streams is lower than introducing and correctly configuring Kafka, especially given no prior Kafka experience.

6. **Cost-effective within current budget**
   - Reusing our existing Redis deployment or modestly scaling it is cheaper than introducing and operating a self-managed Kafka cluster or paying for a managed Kafka service at required reliability levels.

7. **Path to exactly-once semantics for billing notifications**
   - While Redis Streams do not provide global exactly-once guarantees, we can achieve effective exactly-once behavior for billing workflows by:
     - Using **idempotent operations** at the consumer side (e.g., deduplicating by a unique event ID stored in PostgreSQL with a unique constraint).
     - Handling the "generate billing event" and "enqueue event ID to Redis Stream" within a single database transaction (e.g., outbox pattern), ensuring that a billing event is not lost or duplicated from the system of record.
     - Ensuring that sending emails/webhooks is idempotent (e.g., by recording send status keyed by event ID) so that retries do not result in double-charging or duplicate side effects.

## Cons

1. **Weaker long-term scalability and replay capabilities compared to Kafka**
   - Redis Streams are not optimized for very high write throughput (hundreds of thousands to millions of messages per second) or multi-year retention the way Kafka is.
   - Historical replay capabilities are more limited; while Streams support trimming and approximate retention, they are not designed as a long-term event log for analytics or large-scale stream processing.

2. **Operational risk of overloading our existing Redis**
   - Using Redis both for latency-sensitive core workloads (sessions, rate limiting) and for potentially bursty notifications increases blast radius if the Redis instance becomes resource-constrained.
   - We will likely need to separate Redis roles (e.g., dedicated instance/cluster for Streams vs cache) to avoid contention, which adds some infra complexity.

3. **Lack of native exactly-once processing and transactions across consumers**
   - Redis Streams provide at-least-once semantics by design; exactly-once must be achieved via application-level idempotency and outbox-like patterns.
   - Complex workflows that span multiple streams or services may be harder to implement correctly without the transactional/transactional-id semantics Kafka provides.

4. **Less ecosystem support for complex stream processing**
   - Kafka has a mature ecosystem (Kafka Streams, ksqlDB, connectors) for rich stream processing, integrations, and schema management, which we will not leverage.
   - For more advanced patterns (e.g., windowed aggregations, joins), we would need to build custom logic or adopt additional tooling later.

5. **Potential migration cost if we outgrow Redis Streams**
   - If traffic or requirements grow beyond what Redis Streams can comfortably handle, we may need to migrate to Kafka or another streaming platform, incurring future migration cost (dual-write period, consumer changes, etc.).

# Alternatives Considered

## Apache Kafka

Kafka is the de-facto standard for high-throughput, horizontally scalable, durable event streaming. It offers strong ordering guarantees within partitions, high write throughput (millions of messages per second in large clusters), configurable retention policies, consumer groups with offset tracking, and exactly-once processing semantics via idempotent producers and transactional APIs.

We considered Kafka for the notification subsystem but rejected it as the initial choice for the following reasons:

1. **Operational complexity vs team capacity**
   - Operating a reliable Kafka cluster (including brokers, Zookeeper/KRaft, storage, monitoring, and upgrades) is non-trivial and typically requires dedicated infra expertise. Our team of 6 without an infra engineer is not well-positioned to run Kafka in production with high reliability.
   - Misconfigured Kafka (e.g., insufficient replication, incorrect retention settings, under-provisioned disks) can lead to subtle data loss or availability issues that are hard to debug.

2. **Overkill for current scale and requirements**
   - Our projected notification volume (low thousands of messages per second at peak after 10x growth) is well within the capabilities of a Redis Streams setup.
   - Kafka's strengths—very high throughput, very long retention, large numbers of partitions and consumer groups—are more relevant to organizations with much larger data volumes and more complex streaming topologies than our current notification use case.

3. **Time-to-value and learning curve**
   - Introducing Kafka requires standing up new infrastructure, provisioning storage, configuring topics/partitions/replication, integrating with monitoring/logging, and training the team on producer/consumer patterns and failure modes.
   - Given our constraint of delivering value within 2 weeks, the risk of underestimating this effort is high, especially with no prior Kafka experience.

4. **Cost constraints and lack of managed offering at scale**
   - While managed Kafka offerings (e.g., Confluent Cloud, AWS MSK) can reduce operational burden, they come at a cost that is currently outside our budget for full-scale production use.
   - Self-managing Kafka to save costs would shift that burden onto our small team and increase the risk of reliability issues.

5. **Exactly-once semantics can still be achieved with Redis-based design**
   - Although Kafka provides strong exactly-once processing semantics via its transactional producer/consumer APIs, our exact requirements are narrow (billing notifications) and can be satisfied by a combination of the database outbox pattern and idempotent consumers built on Redis Streams.
   - Given that we do not need global exactly-once guarantees for all notification traffic, Kafka's exactly-once features are not compelling enough to justify the added complexity at this stage.

In summary, Kafka remains a strong candidate for future evolution of our messaging and event streaming platform, particularly if our throughput, retention, or cross-service streaming needs grow substantially. For the immediate notification subsystem needs, however, Redis Streams provides a more pragmatic balance of capabilities, cost, and operational simplicity.
