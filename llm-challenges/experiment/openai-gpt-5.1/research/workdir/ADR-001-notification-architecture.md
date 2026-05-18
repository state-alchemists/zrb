# Title
Notification Subsystem Architecture: Apache Kafka vs Redis Streams

# Status
Proposed

# Context
The current notification system sends emails and webhooks synchronously inside the Flask HTTP request cycle. This has led to high request latencies (average ~800ms, spikes up to 8s), cascading failures when downstream providers are slow or unavailable, and silent drops of notifications with no retries or dead-letter queues. Billing-critical notifications (e.g., trial expiry, payment failures) require at-least-once delivery guarantees and exactly-once semantics where feasible, but the current implementation offers neither.

We operate a SaaS project management platform with ~85,000 MAU, ~2M tasks/month, and peak load of ~500 req/s today, with a target of handling 10x this traffic without re-architecting. The backend is a Python/Flask monolith backed by PostgreSQL, with Redis already in production for sessions and rate limiting. The engineering team is six people (3 senior, 3 mid-level) with no dedicated infrastructure engineer and no prior Kafka experience. We have modest budget and cannot rely on premium managed Kafka offerings (e.g., Confluent Cloud at full scale). The new notification subsystem must:

- Decouple notification sending from HTTP request handling via asynchronous processing.
- Provide durable queuing with retry and exponential backoff.
- Offer at-least-once delivery for all billing-related events and exactly-once semantics where feasible.
- Support consumer groups for horizontally scalable workers.
- Facilitate adding real-time WebSocket push notifications within two quarters.
- Fit within ~2 weeks of setup/migration effort before delivering initial value.

We are evaluating Apache Kafka and Redis Streams as the backbone of this notification subsystem.

# Decision
We will adopt Redis Streams as the core messaging mechanism for the notification subsystem, using Redis consumer groups for workers, Redis persistence (AOF) for durability, and application-level idempotency to achieve exactly-once semantics for billing notifications.

Justification:

1. Operational simplicity and team fit: Redis is already part of our stack and operated by the team; introducing Kafka would require provisioning and operating a multi-broker cluster, ZooKeeper-free Kafka (or equivalent), schema registry, monitoring, and backup/restore procedures, which exceeds our current infra capacity. Redis Streams can be enabled on our existing Redis deployment (or a dedicated small Redis instance) with minimal incremental operational overhead.
2. Time-to-value: With no Kafka experience on the team and a two-week setup constraint, the ramp-up and infra work required to safely run Kafka (even using AWS MSK) is unlikely to fit. Redis Streams can be integrated via Python clients (e.g., redis-py) rapidly, and reuse existing observability, security, and deployment patterns.
3. Throughput and scale headroom: Our current and 10x target workloads (from ~500 req/s peak to ~5,000 req/s, with only a fraction of requests generating notifications) are well within the capabilities of a properly sized Redis deployment. While Kafka offers higher absolute throughput and better horizontal scalability for very large event streams, our anticipated notification volume (on the order of tens of thousands of messages per minute at peak) does not justify Kafka’s added complexity.
4. Ordering and consumer groups: Redis Streams provide per-stream append-only ordering and consumer groups, which are sufficient for our notification use cases. We can partition streams by tenant or domain (e.g., billing, activity) when necessary to control contention and ordering scopes.
5. Delivery guarantees and exactly-once semantics: Redis Streams guarantee at-least-once delivery within a consumer group via pending entries and acknowledgment semantics. We can implement exactly-once behavior for billing notifications using application-level idempotency keys stored in PostgreSQL or Redis (e.g., deduplicating on a billing_event_id) combined with transactional updates per notification. Kafka’s exactly-once semantics (EOS) are powerful but require significant configuration (idempotent producers, transactional consumers, careful coordination with sinks) and are overkill relative to our volume and team expertise.

Given our current scale, team size, lack of Kafka expertise, existing Redis footprint, and the two-week constraint, Redis Streams offer the best balance of reliability, delivery guarantees, and operational simplicity.

# Consequences

## Positive consequences

1. Reduced request latency and improved reliability: Offloading notification work to Redis Streams-backed workers will remove external email/webhook calls from the request path, reducing average latency and eliminating current multi-second spikes. Downstream slowness will affect worker throughput rather than HTTP request health.
2. At-least-once delivery with retries: Using consumer groups and pending-entry lists, we can implement retry with exponential backoff and ensure at-least-once delivery for all notifications, including billing-related events, with dead-letter streams for poison messages.
3. Exactly-once semantics via idempotency: For billing notifications, we can store idempotency keys and processing state (e.g., in PostgreSQL or a dedicated Redis hash) to ensure that even if a message is delivered more than once, side effects (email/webhook send + accounting state) are applied only once.
4. Simpler operations: Operating Redis Streams reuses our existing Redis expertise, monitoring, and backup strategies. There is no need to introduce Kafka brokers, topic management, partition rebalancing, or specialized tooling.
5. Faster delivery of new capabilities: Within two weeks, we can likely ship an initial version of the async notification pipeline. Adding WebSocket push notifications later can be done by adding another consumer group to relevant streams without changing the producer side.
6. Cost efficiency: We avoid the cost and operational overhead of running a Kafka cluster or paying for a fully managed Kafka service at our modest scale.

## Negative consequences

1. Less future-proof for extreme scale: If product usage grows orders of magnitude beyond the 10x target (e.g., hundreds of thousands of events per second), Redis Streams may become a bottleneck or require significant re-architecture, whereas Kafka is designed for such high-throughput scenarios.
2. Weaker built-in tooling vs Kafka: Kafka has mature ecosystems (Connect, Schema Registry, ksqlDB, stream processing frameworks) that we will not immediately benefit from. Building integrations (e.g., streaming to data warehouse) may require additional work.
3. Operational risks on existing Redis: If we reuse the existing Redis cluster, notification load could interfere with sessions and rate limiting. We should likely provision a dedicated Redis instance for Streams, adding some operational overhead.
4. No native exactly-once end-to-end semantics: Exactly-once semantics for billing will rely on careful application logic and idempotency patterns instead of Kafka’s transactional guarantees, which increases our own responsibility for correctness and requires careful testing.
5. Limited message retention and replay semantics: While Redis Streams support configurable retention, they are not designed as a long-term event log like Kafka. For long-term analytics or replay requirements, we may need to export data periodically to PostgreSQL or object storage.

# Alternatives Considered

## Apache Kafka

We considered using Apache Kafka as the foundational event streaming platform for notifications and broader event-driven architecture.

Reasons for rejection in this iteration:

1. Operational complexity: Running Kafka in production requires managing a multi-broker cluster, storage volumes, monitoring, upgrades, and careful tuning. Even with managed offerings like AWS MSK, there is significant setup (VPC/LB, IAM, scaling policies) beyond what our 6-person team and lack of infra specialization can comfortably support within two weeks.
2. Team expertise and learning curve: No one on the team has Kafka experience. Designing correct producer/consumer patterns, partitions, consumer groups, and configuring idempotent producers and transactional consumers for exactly-once semantics would require substantial ramp-up and experimentation.
3. Time-to-value constraint: Given the requirement to deliver meaningful improvements within ~2 weeks, the risk that Kafka setup and integration would overrun this timeline is high, especially when considering infrastructure provisioning, staging environment, observability, and failure testing.
4. Overprovisioned for current scale: Kafka shines at very high throughput (hundreds of thousands to millions of messages per second) and complex event-stream architectures. Our anticipated notification volume is moderate, and Redis Streams can handle these loads without the heavyweight infrastructure.
5. Cost considerations: We cannot afford premium managed Kafka (e.g., Confluent Cloud) at full scale, and self-managing Kafka or even running MSK clusters would introduce additional operational cost (larger instances, storage, network) compared to a modestly scaled Redis deployment.

Kafka remains a strong candidate if our traffic and eventing needs grow substantially (e.g., cross-service event sourcing, multi-region streaming, complex stream processing). At that point, we can reevaluate migrating critical streams from Redis to Kafka with better justification for the added complexity.
