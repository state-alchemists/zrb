**Title**

ADR-001: Notification Subsystem Messaging Backbone

**Status**

Proposed

**Context**

Our SaaS project management platform currently sends emails and webhooks synchronously inside the Flask HTTP request cycle. At current scale, this causes high latency, request timeouts, silent notification loss, and cascading failures when downstream providers are slow or unavailable. The system must move notifications to asynchronous processing, add retries with exponential backoff, support dead-letter handling, and be able to serve 10x traffic growth without another architectural rewrite.

The team is small (6 engineers), has no dedicated infrastructure engineer, and has no Kafka experience today. We already operate Redis in production for sessions and rate limiting. We must deliver value within 2 weeks, have a modest budget, and cannot rely on fully managed Confluent Cloud at scale. We also need support for future real-time WebSocket notifications within 2 quarters.

The critical technical requirement is delivery semantics: billing-related notifications require at-least-once delivery at minimum and exactly-once behavior where feasible. In practice, exactly-once end-to-end delivery to external systems such as email providers and webhook receivers cannot be guaranteed solely by the messaging layer; it requires idempotent consumers, deduplication keys, and persistent delivery records in PostgreSQL. The selected messaging system therefore needs to support durable retention, consumer coordination, replay/retry workflows, and operational simplicity for this team.

**Decision**

Choose **Redis Streams** as the notification subsystem backbone.

Redis Streams is the better fit for the current stage of the system because it solves the immediate production problem with the lowest operational and migration cost. The team already runs Redis, so adopting Streams extends an existing platform rather than introducing a new distributed system with ZooKeeper/KRaft, broker sizing, partition planning, monitoring, and on-call burden. That matters more than Kafka's superior theoretical scalability because the business requires value within 2 weeks and the team has no Kafka experience.

Redis Streams provides the core capabilities this subsystem needs now: durable stream persistence, consumer groups, pending message tracking, replay of unacknowledged messages, and retention control. It is more than sufficient for the current load profile and the stated 10x growth target. Even if notification volume grows roughly with traffic, the workload remains well within Redis Streams territory for a single application subsystem, especially compared with Kafka deployments that are typically justified by much larger event platform needs.

On technical properties:
- **Throughput**: Kafka has higher ceiling throughput and better horizontal scale via partitions, but the current platform peak (~500 req/s) and a 10x target do not justify that overhead yet. Redis Streams can comfortably support notification workloads of this size.
- **Ordering guarantees**: Redis Streams preserves stream order, and consumer groups can process messages predictably for this use case. Kafka offers stronger partition-based ordering at large scale, but that advantage is not decisive for the current notifier workload.
- **Message retention**: Kafka is stronger and more flexible for long-term retention and replay. For notifications, we primarily need bounded retention long enough for retries, recovery, and audit support; Redis Streams is adequate when combined with PostgreSQL delivery logs for durable business history.
- **Consumer groups**: Both support consumer group patterns. Redis Streams' pending entries list and claim/ack flow are sufficient for retrying stuck notification jobs.
- **Exactly-once semantics**: Kafka offers stronger native exactly-once semantics for Kafka-to-Kafka processing through idempotent producers and transactional writes, but it does not give true exactly-once delivery to external email/webhook systems. Because billing notifications terminate in external side effects, we need application-level idempotency and a PostgreSQL-backed notification ledger regardless of broker choice. That reduces Kafka's biggest advantage in this specific design.
- **Operational complexity**: Redis Streams is materially simpler for a 6-person team already running Redis. Kafka would add significant operational surface area and learning curve, likely violating the 2-week delivery constraint.

Therefore, Redis Streams is the best decision for this ADR, paired with application-level idempotency keys and a PostgreSQL notification-delivery table to enforce exactly-once behavior for billing notifications where feasible.

**Consequences**

Pros:
- Fastest path to decouple notifications from HTTP requests and reduce latency/timeouts.
- Reuses existing Redis operational knowledge and infrastructure.
- Lower setup and migration risk for a team without Kafka experience.
- Supports consumer groups, retries, redelivery of unacked messages, and dead-letter patterns with modest implementation effort.
- Good fit for near-term roadmap, including async email/webhook processing and future WebSocket push notifications.
- Lower cost than introducing Kafka infrastructure now.
- Sufficient throughput for current scale and likely 10x growth of this notification workload.
- Simplifies delivering value inside the 2-week constraint.

Cons:
- Weaker long-term event streaming platform than Kafka for very large scale or broad multi-team event-driven architectures.
- Retention and replay capabilities are less robust than Kafka's log-centric model.
- Exactly-once guarantees are not native for external side effects and must be implemented in application logic with PostgreSQL-backed deduplication.
- Less flexible horizontal scaling and parallelism than Kafka's partition model if the notification system grows into a much larger event backbone.
- Redis will now carry more production-critical workload, so capacity planning and isolation become more important.

**Alternatives Considered**

**Apache Kafka** was rejected for now.

Kafka is technically stronger in several dimensions: very high throughput, durable retention, partition-based ordering, strong consumer group semantics, broad ecosystem support, and exactly-once semantics for transactional stream processing. If this were a larger platform team building a company-wide event backbone, Kafka could be the right long-term choice.

However, it is the wrong choice under the current constraints. Kafka introduces substantially higher operational complexity, including broker management, replication planning, storage sizing, monitoring, alerting, and production tuning. The team has no Kafka experience and no dedicated infrastructure engineer, which raises delivery and reliability risk. It is also unlikely to fit comfortably into the requirement of shipping within 2 weeks. Finally, Kafka's exactly-once semantics do not solve the hardest requirement by themselves because billing notifications end in external email/webhook side effects; those still require application-level idempotency and a database-backed delivery ledger. Given that Redis Streams already satisfies the immediate needs with much lower cost and complexity, Kafka is not justified at this stage.
