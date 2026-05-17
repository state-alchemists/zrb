# Title

Notification Subsystem Architecture: Kafka vs Redis Streams

# Status

Proposed

# Context

Our SaaS project management platform currently handles notifications (emails and webhooks) synchronously within the HTTP request cycle of a Python/Flask monolith backed by PostgreSQL and Redis. With ~85,000 MAUs, ~2M tasks/month, and peak traffic of ~500 req/s, this design has led to:
- High latency (average 800ms, spikes to 8s) due to outbound notification calls blocking request completion.
- Silent failures when downstream providers are unavailable, with no retry or dead-letter handling.
- Cascading failures when slow webhook endpoints exhaust connection pools and impact unrelated features.
- Lack of delivery guarantees, despite a requirement for at-least-once delivery for billing events and exactly-once semantics where feasible.

We need to introduce an asynchronous notification subsystem that:
- Decouples notification processing from the HTTP request cycle.
- Supports retry with exponential backoff and dead-letter handling.
- Provides at-least-once delivery for all billing-related notifications and exactly-once semantics for billing notifications end-to-end where feasible.
- Can support real-time WebSocket push notifications within two quarters.
- Can scale to ~10x current traffic without major re-architecture.

Constraints:
- Small engineering team: 6 engineers (3 senior, 3 mid-level) and no dedicated infrastructure engineer.
- Existing Redis deployment in production (for sessions and rate limiting).
- No Kafka experience on the team; introducing Kafka would require learning, operating, and monitoring a new distributed system.
- Setup/migration budget of approximately 2 weeks before first production value.
- Modest infrastructure budget; fully managed Kafka offerings at the required scale are not affordable today.
- Billing notifications must achieve exactly-once semantics from the perspective of external side effects (no duplicate billing emails or duplicate webhook calls that could cause double-charging or inconsistent state).

We are evaluating two options for the notification backbone: Apache Kafka and Redis Streams.

# Decision

Adopt Redis Streams as the primary backbone for the notification subsystem, using consumer groups for worker scaling, Redis persistence for retention, and application-level idempotency keys and deduplication to provide exactly-once semantics for billing notifications.

Redis Streams is chosen over Apache Kafka because it better matches our current scale, team expertise, and operational constraints while still providing the necessary delivery guarantees and scalability for the next 2–3 years. Specifically:
- Throughput and scale: Our projected notification volume (derived from ~2M tasks/month and 10x growth) is well within Redis Streams’ practical throughput on a modestly sized Redis cluster (hundreds of thousands to a few million messages per minute) without requiring Kafka’s higher-end throughput capabilities.
- Ordering and consumer groups: Redis Streams provide per-stream (and implicitly per-partition via sharding by key) ordered message delivery and consumer groups, which are sufficient for ordering guarantees on per-tenant or per-billing-entity streams.
- Delivery guarantees: Redis Streams natively support at-least-once delivery via consumer groups and pending entries lists. We can layer application-level idempotency (using Redis or PostgreSQL) to achieve exactly-once semantics for billing notifications.
- Operational complexity: Redis is already in production and familiar to the team, so extending its use to Streams introduces far less operational risk and cognitive load than standing up and operating a Kafka cluster (ZooKeeper-less but still multi-broker, with topics, partitions, retention policies, brokers, and client tuning).
- Time to value: We can prototype and deploy a Redis Streams–based notification pipeline within the two-week budget by reusing existing Redis infrastructure, libraries, and operational knowledge. Kafka adoption would likely exceed this window due to provisioning, security, observability, client integration, and failure-mode testing.

# Consequences

## Pros

1. Lower operational complexity
   - We build on an existing Redis deployment and team familiarity, reducing the need to operate and monitor a new distributed system (Kafka brokers, controllers, partitions, replication, etc.).
   - Fewer moving parts (no separate Kafka cluster, schema registry, Kafka Connect) simplifies incident response and maintenance for a small team without an infra specialist.

2. Sufficient throughput and scalability for our horizon
   - At current and 10x projected load, notification event volume is unlikely to saturate a properly sized Redis instance or small cluster; Redis Streams can handle tens-of-thousands of ops/sec on commodity hardware.
   - Horizontal scaling can be handled via logical partitioning of streams (e.g., per-tenant or per-domain streams) and multiple consumer groups/workers.

3. Strong enough ordering guarantees
   - Redis Streams preserves ordering within a stream. By partitioning by business key (e.g., billing account, project, or user), we can ensure ordered delivery for events that require it (e.g., “trial started” → “trial expiring” → “trial expired”).
   - Consumers can process events in a deterministic order per key, which is sufficient for our notification workflows.

4. Delivery guarantees and exactly-once semantics via app-level design
   - Redis Streams consumer groups provide at-least-once delivery via pending-entry tracking and message claiming on failure.
   - We can implement exactly-once semantics for billing notifications by:
     - Assigning an idempotency key per billing event (e.g., UUID or combination of tenant ID + event ID).
     - Storing processed-event keys in PostgreSQL or Redis with a unique constraint or SETNX semantics.
     - Ensuring the notification processor checks and records processing under a single transaction or atomic operation before invoking external side effects (email provider, billing webhook), and only performing the side effect once per key.

5. Faster path to async decoupling and retries
   - Pushing notification events into Redis Streams from the Flask app is straightforward (single library, minimal configuration), enabling us to remove blocking notification calls from the HTTP path quickly.
   - Retry with exponential backoff can be implemented with stream-based retry queues (e.g., dead-letter stream plus scheduled requeue using sorted sets or a lightweight scheduler worker) without needing Kafka-specific tooling.

6. Integration with future WebSocket push notifications
   - The WebSocket service can consume from the same Redis Streams or from derivative streams, allowing unified event distribution for email, webhook, and real-time push channels without an additional messaging layer.

## Cons

1. Less “future-proof” for extreme scale
   - Kafka is purpose-built for very high-throughput, large-scale event streaming with strong durability guarantees and long retention on disk. If we significantly exceed the anticipated 10x growth (e.g., orders of magnitude more events), Redis Streams may become a bottleneck or operationally complex to scale and shard correctly.

2. Operational risk of multi-use Redis
   - Using Redis both for critical notification streams and for sessions/rate limiting increases blast radius; a Redis outage or resource exhaustion now affects more subsystems.
   - We will need strong resource isolation (separate Redis instances or clusters, or at minimum separate DBs and careful capacity planning) and stricter monitoring.

3. Weaker built-in tooling for long-term retention and replay
   - Kafka excels at long-term log retention, time-based and size-based topic management, and straightforward replays for backfills and new consumers.
   - Redis Streams can support retention via MAXLEN and trimming, but they are not designed for months-long full-history retention at large scale; we will likely enforce shorter retention windows and rely on PostgreSQL for durable audit logs of billing events.

4. Exactly-once semantics not fully native
   - Kafka offers stronger built-in primitives for exactly-once processing (idempotent producers, transactional producers/consumers) in some client libraries, though they are complex to use correctly.
   - With Redis Streams, we must implement idempotency and deduplication at the application level, which adds code and testing complexity and requires careful design of transactional boundaries.

5. Potential limits on consumer group scaling
   - For very high parallelism, Redis Streams consumer groups may be less efficient than Kafka’s partition-based consumer groups, which are designed for large numbers of consumers and partitions.
   - We may need to carefully design stream partitioning and worker assignment to avoid hot spots.

# Alternatives Considered

## Apache Kafka

We considered adopting Apache Kafka as the backbone for the notification subsystem.

Pros of Kafka in our context:
- Very high throughput and horizontal scalability: Kafka is proven at millions of messages per second with proper partitioning and cluster sizing, and would handle any reasonable future growth of our notification volume.
- Strong durability and long-term retention: Kafka persists messages to disk with configurable replication and retention, making it suitable for event sourcing patterns, audit logs, and replaying history for new consumers or backfills.
- Mature ecosystem: Rich ecosystem of connectors, stream processing frameworks (Kafka Streams, ksqlDB), and monitoring tools could unlock future use cases (analytics, event-driven workflows) beyond notifications.
- Consumer group model and ordering: Kafka provides ordered delivery within partitions and well-defined consumer group semantics, which align well with worker scaling patterns.
- Exactly-once processing semantics: Modern Kafka clients support idempotent producers and transactional processing that can approximate exactly-once delivery semantics end-to-end, especially for internal data pipelines.

Reasons for rejecting Kafka for this decision:
- Operational complexity beyond current team capacity: Operating a reliable Kafka cluster (even a small one) entails managing brokers, partitions, replication, monitoring, broker upgrades, and tuning. With no existing Kafka experience and no dedicated infra engineer, this introduces significant operational risk.
- Time-to-value exceeds 2-week constraint: Standing up secure Kafka infrastructure (whether self-managed on AWS or via a managed but cost-constrained provider), configuring topics and ACLs, integrating with the Python monolith, and validating failure modes would reasonably exceed the two-week window for initial value.
- Cost constraints: Fully managed Kafka offerings (e.g., Confluent Cloud) at production scale are currently outside our budget. Self-hosting Kafka to reduce cost would further increase operational burden.
- Over-provisioned for current use case: Our notification volume and 10x growth target do not require Kafka’s extreme throughput and long-term retention capabilities today. Choosing Kafka now would prioritize theoretical future scalability over the immediate need to reduce request latency and ensure delivery guarantees.
- Added cognitive load: Kafka concepts (topics, partitions, consumer groups, offsets, retention, compaction, transactions) and operational practices would demand substantial learning time from the entire team, detracting from product feature delivery.

Given these factors, Kafka is not the right fit for the current stage of the product and team. Redis Streams offers a more lightweight, lower-risk path to meeting our notification requirements within the specified constraints, while keeping open the option to introduce Kafka in the future if our scale and team capacity materially change.
