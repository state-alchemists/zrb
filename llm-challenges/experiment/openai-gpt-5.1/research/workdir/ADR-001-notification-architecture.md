# Title

Notification Subsystem Architecture: Kafka vs Redis Streams

# Status

Proposed

# Context

The current notification subsystem is implemented synchronously inside the HTTP request cycle of our Python/Flask monolith. When tasks are updated, assigned, or completed, the application sends emails and webhooks inline with the request. This has led to:

- High and highly variable latency (average 800ms, spikes up to 8s) because outbound network calls to email providers and webhook endpoints block the HTTP response.
- Silent failures when downstream providers are unavailable; notifications are dropped without retries or dead-letter handling.
- Cascading failures where slow or stuck webhook endpoints exhaust the backend's connection pools and impact unrelated features.
- Lack of delivery guarantees for billing-critical events (e.g., trial expiry, failed payments), where we need at-least-once delivery and, where feasible, exactly-once semantics.

We need to introduce an asynchronous notification subsystem that:

- Decouples notification production from HTTP request handling via a durable message log or queue.
- Supports retry with exponential backoff and dead-letter queues for failed notifications.
- Provides at-least-once delivery guarantees for all billing events and the ability to implement exactly-once semantics end-to-end for billing notifications.
- Can support additional real-time WebSocket push notifications within two quarters without major re-architecture.
- Can scale to at least 10x current traffic (~5,000 req/s, ~20M+ notification-related events per month) with predictable latency and without a fundamental redesign.

Constraints and environment:

- Engineering team: 6 developers (3 senior, 3 mid-level) with no dedicated infrastructure or SRE role.
- We already operate Redis in production for session storage and rate limiting.
- There is no Kafka operational or development experience on the team today.
- Initial setup and migration must deliver value within 2 weeks of effort.
- Budget is modest; we cannot rely on fully managed, premium Kafka offerings (e.g., Confluent Cloud at our projected scale).
- We must maintain exactly-once semantics for billing notifications (in practice, idempotent processing with at-least-once delivery and deduplication).

Within this context, we are evaluating two options for the notification subsystem message backbone:

1. Apache Kafka
2. Redis Streams

# Decision

We will implement the notification subsystem on top of Redis Streams, using our existing Redis deployment and extending it with consumer groups, durable streams, and retry/dead-letter patterns.

Justification:

1. Operational complexity and team fit
   - Kafka requires operating a multi-broker cluster (or paying for a fully managed service) with ZooKeeper or KRaft, dedicated storage, and careful tuning for replication, retention, and partitioning. This is a non-trivial operational burden, especially without prior Kafka experience or a dedicated infra engineer.
   - Redis Streams, by contrast, can be enabled on our existing Redis deployment with modest configuration changes (e.g., memory limits, eviction policy, RDB/AOF configuration). Operationally it is much closer to what the team already understands.
   - Given the 2-week setup/migration constraint, the learning curve and infra work for Kafka (including provisioning, monitoring, schema decisions, client libraries, and deployment pipelines) makes Kafka unlikely to deliver value within that window.

2. Throughput and scalability
   - Our projected scale (10x current traffic, roughly up to ~5,000 notification-related events per second at peak) is well within the practical capabilities of a properly sized Redis instance or small Redis cluster using Streams. Benchmarks and production usage indicate Redis Streams can comfortably handle tens of thousands of operations per second on modest hardware.
   - Kafka does scale better and more predictably to very high sustained throughput (hundreds of thousands to millions of messages per second) with longer retention; however, our near- to medium-term needs do not justify adopting that level of complexity now.

3. Ordering and consumer model
   - Both Kafka and Redis Streams provide per-partition/per-stream ordering. For notifications, strict global ordering is not required; per-entity or per-recipient ordering is sufficient and can be modeled using streams or stream keys.
   - Redis Streams consumer groups allow us to create logical consumer groups per notification type (e.g., billing, email, webhooks, websocket push) with multiple consumers sharing the load while preserving ordering within a given shard key.

4. Delivery guarantees and exactly-once semantics
   - Kafka shines in providing strong durability and, with idempotent producers and transactional APIs, near "exactly-once" processing semantics between Kafka and certain sinks. However, end-to-end exactly-once delivery is still application-level and will require idempotency keys and deduplication logic in any case.
   - Redis Streams supports at-least-once delivery semantics via XREADGROUP, pending entries list (PEL), and explicit acknowledgements. We can implement robust retry with exponential backoff by moving failed messages to dedicated retry streams with scheduled reprocessing, and a dead-letter stream for permanently failing messages.
   - Exactly-once semantics for billing notifications can be achieved by:
     - Using at-least-once delivery with idempotent operations at the consumer side (e.g., a unique billing_event_id stored in PostgreSQL and checked before applying side-effects).
     - Ensuring that producing to Redis Streams and committing the corresponding billing state in PostgreSQL are coordinated (e.g., outbox pattern: write billing state + notification event to the DB in a single transaction, then a background worker publishes from the DB outbox to Redis Streams). This pattern works equally well with Redis Streams and does not rely on Kafka's transactional API.

5. Time-to-value and complexity of integration
   - Redis Streams can be integrated directly using mature Python clients (e.g., redis-py) and does not require introducing additional dependencies like Kafka brokers, Kafka Connect, or schema registries.
   - The team can implement a minimal but production-ready notification pipeline (producer wrapper, stream definitions, consumer workers, retry/dead-letter handling, monitoring) within the 2-week constraint because it builds on existing Redis operations knowledge and infrastructure.
   - Kafka would likely require more time to set up infrastructure, gain familiarity with client libraries and configuration, and design topics/partitions/replication factors and retention strategies.

6. Cost
   - Leveraging the existing Redis deployment (potentially scaled up or configured as a small AWS-managed Redis cluster) is cost-effective relative to provisioning and operating a Kafka cluster or using a fully managed Kafka service at our projected scale.
   - Avoiding Kafka at this stage also avoids the need for additional monitoring, logging, and expertise specifically around Kafka, which would increase both direct and indirect (operational) costs.

Given these factors, Redis Streams provides sufficient throughput, ordering, and delivery semantics for our current and 10x target load while fitting our team's skills, time constraints, and budget. Kafka remains a strong candidate for a future evolution if our throughput or retention requirements grow substantially beyond Redis's sweet spot.

# Consequences

Positive consequences:

- Rapid decoupling of notifications from the HTTP request cycle by writing notification events to Redis Streams instead of performing synchronous email/webhook calls, reducing request latency and eliminating most request timeouts.
- At-least-once delivery semantics for all notifications via Redis Streams consumer groups, pending-entry tracking, and explicit acknowledgements.
- Practical exactly-once semantics for billing notifications via idempotent consumer logic and the outbox pattern, without relying on Kafka's transactional APIs.
- Leverages existing Redis infrastructure and team expertise, minimizing operational risk and onboarding time.
- Lower infrastructure cost and complexity compared to running a Kafka cluster, especially given our modest scale and lack of Kafka experience.
- Flexible consumer group model that supports independent scaling and deployment of different notification processors (email, webhook, billing, websocket push) while preserving ordering where needed.
- Straightforward path to adding WebSocket push notifications: a websocket gateway service can subscribe to a dedicated Redis Stream (or consumer group) and push events to connected clients in near real-time.

Negative consequences / trade-offs:

- Redis Streams does not match Kafka's durability and horizontal scalability for extremely high throughput and long-term retention use cases. If our usage grows far beyond the 10x target (e.g., orders of magnitude more events or multi-week/month retention at scale), we may need to revisit Kafka or another log-based system.
- Redis is primarily an in-memory data store; while Streams can be persisted via AOF/RDB and can handle disk-backed data, careful configuration is required to avoid memory pressure and eviction issues, especially under bursty workloads.
- Operational patterns (backup, monitoring, alerting, capacity planning) for Redis Streams at higher volume need to be developed; the team must be disciplined about stream trimming policies (e.g., MAXLEN) and retention, which is less opinionated than Kafka's log retention model.
- We will not benefit from Kafka's mature ecosystem (Kafka Connect, ksqlDB, ecosystem of connectors) for integrating with other systems; any additional integrations or stream processing will need to be built in-house or with other tools.
- Migration to Kafka later, if required, will incur additional engineering effort to reimplement producers/consumers and migrate notification topics/streams; however, a clean abstraction around the messaging layer can mitigate this cost.

# Alternatives Considered

## Apache Kafka

We considered using Apache Kafka as the backbone for the notification subsystem.

Reasons for not choosing Kafka at this time:

1. Operational complexity vs team capacity
   - Running Kafka (even a small cluster) reliably requires expertise in broker configuration, partitioning strategy, replication, storage management, monitoring, and failure recovery. Our team has no Kafka experience and no dedicated infra engineer, making it risky to adopt as a core dependency.
   - While managed Kafka offerings exist (e.g., AWS MSK, Confluent Cloud), our budget constraints limit our ability to use fully managed, premium configurations that would sufficiently reduce operational burden.

2. Time-to-value
   - Standing up Kafka (even with AWS MSK) and integrating it into our stack (topic design, client configuration for Python, observability, security, CI/CD) is unlikely to be achieved with confidence in under 2 weeks given our current experience level.
   - In contrast, Redis Streams can be adopted incrementally on top of our existing Redis infrastructure, making it much easier to meet the 2-week setup/migration requirement.

3. Over-provisioned capabilities for current needs
   - Kafka's strengths — extremely high throughput, large-scale multi-tenant event streaming, long-term log retention, exactly-once producer/consumer transactions — are more than we require for the notification subsystem at our current and near-term projected scale.
   - Our primary goals are decoupling, at-least-once delivery, retries with backoff, and practical exactly-once semantics for a subset of events. These are achievable with Redis Streams plus application-level idempotency and a DB outbox pattern.

4. Cost
   - Kafka clusters (self-managed or via MSK) require dedicated compute and storage resources, plus operational overhead. Given our modest scale and budget, it is more cost-effective to extend our existing Redis setup.

For these reasons, Kafka is not selected as the notification subsystem backbone at this time. We may revisit Kafka (or a managed streaming platform) if our event volume, retention requirements, or cross-system streaming needs grow to a point where Redis Streams is no longer sufficient or cost-effective.
