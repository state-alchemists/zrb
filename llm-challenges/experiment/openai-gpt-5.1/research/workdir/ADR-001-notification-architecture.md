# Title

Notifier Subsystem Message Backbone: Kafka vs Redis Streams

# Status

Proposed

# Context

Our current Flask monolith sends emails and webhooks synchronously in the HTTP request cycle. This causes high tail latency (p99 up to 8s), occasional timeouts, and cascading failures when email providers or webhook endpoints are slow or unavailable. Notifications can also be silently dropped, and we have no retries, dead-letter queues, or delivery guarantees.

We need to introduce an asynchronous notification subsystem that:
- Decouples notification production from delivery so web requests return quickly
- Provides at-least-once delivery for all notifications and exactly-once semantics for billing-critical events where feasible
- Supports retries with exponential backoff and dead-letter queues for poison messages
- Can later fan out to additional consumers (e.g., WebSocket push notifications) without re-architecting
- Scales to at least 10x the current load (~500 req/s peak today) without a fundamental redesign

Constraints:
- Small team (6 engineers, no dedicated infra) with no Kafka experience
- Redis already runs in production for sessions and rate limiting
- Modest budget; cannot rely on high-cost managed Kafka (e.g., Confluent Cloud at full scale)
- We must deliver tangible value from the new system within ~2 weeks of engineering effort

We are choosing between Apache Kafka and Redis Streams as the primary message backbone for the notifier subsystem.

# Decision

Use **Redis Streams** as the primary messaging backbone for the notification subsystem.

Redis Streams provides sufficient throughput and durability for our current and 10x projected notification load while minimizing operational complexity and upfront cost. It leverages our existing Redis infrastructure and skills, enabling us to deliver an asynchronous, reliable notifier within the 2-week constraint.

Exactly-once semantics for billing notifications will be achieved at the application level using idempotent operations and message de-duplication (idempotency keys stored in PostgreSQL or Redis), layered on top of Redis Streams’ at-least-once delivery.

Kafka is more feature-rich for high-scale event streaming and complex topologies but introduces substantial operational and conceptual overhead for a small team without prior Kafka experience. Meeting our setup timeline and cost constraints with self-managed Kafka would be risky.

# Consequences

## Pros

1. **Fast time-to-value**
   - We can reuse the existing Redis cluster: no new network surface area, VPC configuration, or base images.
   - Redis Streams API is relatively simple; Python clients (e.g., redis-py) support XADD/XREADGROUP/XACK out of the box.
   - Implementing a basic producer–consumer flow with consumer groups, retries, and a dead-letter stream is feasible within the 2-week window.

2. **Operational simplicity**
   - One fewer distributed system to operate; we already monitor and backup Redis.
   - Scaling can initially be vertical (larger instance) and later horizontal using Redis Cluster or sharding streams by tenant or notification type.
   - No need to operate ZooKeeper / KRaft, brokers, and schema registry clusters.

3. **Adequate performance and durability for our needs**
   - Redis Streams can easily handle thousands to tens of thousands of messages per second on a modest node, well beyond our current and 10x projected notification volume.
   - Stream entries are appended and persisted to disk (AOF/RDB) with configurable durability guarantees. For notification workloads, this is sufficient, especially with regular backups and multi-AZ deployment.
   - Consumer groups give us partition-like semantics with ordered delivery per consumer group and support for multiple independent consumers (e.g., email worker pool, webhook worker pool, WebSocket push workers).

4. **Simpler integration for exactly-once-like semantics**
   - For billing notifications, we can use a combination of:
     - Idempotency keys stored in PostgreSQL (e.g., a `billing_notifications` table keyed by event ID) to ensure each event results in at most one state change or outbound notification per channel.
     - At-least-once processing via Redis Streams consumer groups; if a consumer crashes, pending messages can be claimed by another consumer.
     - Outbox pattern (write billing events and idempotency keys in the same DB transaction as billing changes, then publish to Redis Streams asynchronously) to avoid losing events between DB commit and enqueue.
   - This provides effectively exactly-once externally observable behavior without depending on Kafka’s transactional APIs.

5. **Cost control**
   - No additional managed service subscription is required initially.
   - We can scale Redis cost gradually as traffic grows, instead of a step-function cost increase from provisioning a Kafka cluster or a high-throughput managed plan.

## Cons

1. **Weaker native guarantees vs Kafka**
   - Kafka offers stronger durability and replay semantics (e.g., replicated logs, long retention with efficient disk usage, log compaction) designed for event streaming and analytics use cases.
   - Redis Streams retention is primarily length- or time-based and, under memory pressure or misconfiguration, old entries may be trimmed aggressively.
   - There is no built-in exactly-once processing; we rely on application-level idempotency.

2. **Scaling trade-offs**
   - Kafka scales throughput horizontally very well via partitioning and consumer groups across brokers. Redis can scale, but horizontal scaling usually requires more careful sharding/cluster management and has more limits on maximum stream size per shard.
   - If we reach very high sustained throughput (e.g., 100k+ msg/s across many topics) and long retention, Redis memory and I/O usage may become a bottleneck or cost driver.

3. **Less suitable for long-term event retention and analytics**
   - Kafka is better suited if we later want to treat all notifications as part of a broader event bus for analytics, event sourcing, or stream processing (e.g., using Kafka Streams, Flink, ksqlDB).
   - With Redis Streams we will likely need a separate data pipeline (e.g., shipping events to S3/warehouse) if long-term, replayable history or complex stream processing becomes a requirement.

4. **Potential Redis blast radius**
   - Co-locating streams with existing Redis usage increases the risk that notification traffic could impact sessions or rate-limiting if not isolated (e.g., by using separate logical DBs or a dedicated Redis instance/cluster).
   - We must implement quotas, monitoring, and backpressure to protect core services.

# Alternatives Considered

## Apache Kafka

**Why we considered it**
- Kafka is the industry-standard event streaming platform, with:
  - Very high throughput (hundreds of thousands to millions of messages per second on multi-broker clusters).
  - Strong ordering guarantees per partition and durable, replicated logs suitable for long-term retention.
  - Native consumer groups with offset tracking, replay from arbitrary offsets, and support for multiple independent consumer applications.
  - Transactional producers and exactly-once semantics (EOS) in Kafka Streams for end-to-end exactly-once processing.
  - Rich ecosystem for stream processing and integration (Kafka Connect, Kafka Streams, Flink, etc.).

**Why we rejected it for now**
1. **Operational complexity and team experience**
   - We have no Kafka experience on the team and no dedicated infra engineer. Standing up, securing, and operating a production-grade Kafka cluster (brokers, ZooKeeper/KRaft, monitoring, upgrades, partition rebalancing, disk management) is non-trivial.
   - The learning curve for Kafka concepts (topics, partitions, consumer groups, offset management, transactions, compaction/retention tuning) is steep relative to Redis Streams.
   - Relying on self-managed Kafka within a 2-week setup window is high-risk, especially given our availability requirements.

2. **Cost and managed options**
   - Fully managed Kafka offerings (e.g., Confluent Cloud, Amazon MSK Serverless) reduce operational overhead but come with ongoing costs that conflict with our “modest budget” constraint at our projected scale.
   - Even managed Kafka still requires architectural work (VPC peering, IAM, data governance, topic/partition design, observability) that would push us beyond the 2-week target for initial value.

3. **Over-provisioned for our current needs**
   - Our current and 10x traffic targets for notifications are well within Redis Streams’ capabilities. We do not currently need multi-tenant, multi-region, analytics-heavy event streaming that Kafka excels at.
   - Kafka’s strongest features (very long-term retention, complex stream processing, large numbers of partitions) are not required for the notification subsystem in the next 12–24 months.

4. **Exactly-once semantics do not strictly require Kafka**
   - While Kafka can support exactly-once processing in certain end-to-end pipelines, achieving truly exactly-once delivery to external systems (email providers, webhook endpoints) still requires idempotency on the consumer side.
   - Given we must implement idempotency and deduplication in our application regardless, Kafka’s EOS support would not eliminate the need for application-level safeguards.

**Future considerations**
- If, in the future, we:
  - Use notifications as part of a broader event bus for analytics and ML features, or
  - Need multi-region replication and very long retention, or
  - Outgrow Redis Streams’ performance and operational sweet spot,

  we can reassess introducing Kafka as a central event streaming platform. At that point, we can build a bridge from Redis Streams (or our DB outbox) into Kafka, migrating consumers incrementally.

In summary, Redis Streams aligns better with our team size, skills, budget, and timeline while meeting our reliability and scale requirements for the notifier subsystem. Kafka remains a viable future option if our event streaming needs expand significantly.
