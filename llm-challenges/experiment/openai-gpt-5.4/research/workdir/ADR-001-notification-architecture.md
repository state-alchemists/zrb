Title

ADR-001: Notification Subsystem Architecture — Redis Streams over Apache Kafka

Status

Proposed

Context

The current notification subsystem runs synchronously inside the Flask request cycle and is now a production risk. Notification delivery for emails and webhooks adds substantial latency to user-facing requests, with average response times around 800 ms and spikes up to 8 seconds during business-hour peaks. It also fails unsafely: provider outages or slow webhook endpoints can drop notifications without retry and have already caused cascading failures severe enough to exhaust connection pools and impact unrelated features.

The replacement design must decouple notification work from HTTP requests, support retries with exponential backoff, and provide durable asynchronous processing. It must also support at-least-once delivery for general notifications and exactly-once behavior for billing-critical notifications such as trial expiry and payment failure events, where duplicate customer communication is unacceptable.

The system must scale to roughly 10x current traffic without another architectural rewrite. Current traffic is approximately 500 requests/second at peak, with about 2 million tasks created per month. Within two quarters, the platform also needs real-time WebSocket push notifications, so the chosen subsystem should support multiple consumers and fan-out patterns without forcing a second messaging migration.

The decision is constrained by execution reality. The engineering team has 6 people, with no dedicated infrastructure engineer. The team already operates Redis in production for sessions and rate limiting, but has no Kafka experience. The first version must deliver value within 2 weeks of setup and migration effort, and the budget does not support a fully managed Kafka offering such as Confluent Cloud at the expected scale.

Decision

Choose Redis Streams as the notification subsystem backbone.

Redis Streams is the better fit for the current constraints because it solves the immediate production failures with the least operational and migration risk. The team already runs Redis, so adopting Streams adds new application patterns but not a new distributed system. That matters more here than Kafka’s stronger long-term event-platform capabilities. A small team with no Kafka experience is unlikely to stand up, tune, monitor, and safely operate Kafka within the required 2-week delivery window.

Technically, Redis Streams provides the core capabilities this subsystem needs now: append-only message storage, consumer groups, pending-entry tracking, replay of unacknowledged work, and enough throughput to comfortably handle the current load and near-term growth target for notifications. Redis can process very high in-memory throughput, and the notification workload described here is moderate compared with what either system can support. Ordering guarantees are also sufficient: Redis Streams preserves order within a stream, and consumer groups allow controlled parallelism. For notification processing, per-stream or per-entity ordering is generally enough, whereas Kafka’s partition-based ordering model would only become materially superior if this subsystem evolved into a broader event platform with many independent high-volume consumers.

Redis Streams does not provide Kafka-style end-to-end exactly-once semantics. However, Kafka would not by itself solve the business requirement either, because exactly-once customer-visible notification delivery still depends on application-side idempotency at the sink boundary, especially for email and webhook providers. The practical design should therefore use an outbox/idempotency pattern backed by PostgreSQL for billing-critical events: persist a unique billing notification record in the same database transaction as the business event, publish asynchronously to Redis Streams, and have workers enforce idempotent delivery using a stable event key and a sent-log table with unique constraints. This yields effectively exactly-once behavior for billing notifications at the application level, which is the level that actually matters.

Kafka’s advantages are real: stronger retention semantics, better horizontal scalability through partitions, more mature replay for long-lived event streams, and native exactly-once semantics for Kafka-to-Kafka processing. But those strengths are mismatched to the current decision horizon. The immediate problem is not raw throughput; it is operational simplicity, time-to-value, and safe asynchronous execution. Redis Streams meets those needs while leaving open a future migration path if notification traffic or event-platform ambitions outgrow it.

Consequences

Pros:
- Fastest path to production because Redis is already deployed and understood by the team.
- Lower operational complexity than Kafka: no brokers, partitions, ZooKeeper/KRaft operational learning curve, or separate platform to monitor and tune.
- Consumer groups and pending-entry lists support asynchronous workers, retries, and recovery from worker crashes.
- Retention can be bounded intentionally, which is appropriate for transient notification workloads rather than indefinite event archival.
- Sufficient throughput for current notification volume and likely 10x growth, assuming notifications remain a subsystem rather than a company-wide event bus.
- Easy to add additional consumers later for WebSocket push notifications, email delivery, webhook dispatch, and audit/metrics side processing.
- Lower cost than self-managing or paying for managed Kafka under current budget constraints.

Cons:
- No native end-to-end exactly-once semantics; billing-critical flows still require application-level idempotency and a PostgreSQL-backed outbox/sent-log design.
- Retention and replay capabilities are weaker than Kafka for long-lived event history, broad analytics use cases, or large-scale backfills.
- Ordering guarantees are simpler but less flexible than Kafka’s partition model for very high parallelism workloads.
- Redis is primarily an in-memory system; durable retention at larger scale is less natural and may pressure memory if stream growth is not carefully bounded.
- Operationally simpler than Kafka, but still not free: worker crash recovery, dead-letter handling, retry scheduling, and monitoring must be implemented deliberately.

Alternatives Considered

Apache Kafka was rejected for now.

Kafka is the stronger platform if the notification subsystem is expected to become a high-scale, multi-team event backbone with long retention, heavy replay needs, and many independent consumers. It offers durable log retention, partition-based horizontal scale, ordered consumption within partitions, mature consumer groups, and exactly-once semantics for specific Kafka transactional workflows. For very large throughput and event streaming use cases, Kafka is the more extensible choice.

However, those benefits do not outweigh the delivery and operational costs in this context. The team has no Kafka experience, no dedicated infrastructure engineer, a strict 2-week window to show value, and a modest budget that rules out the easiest managed option. Self-managing Kafka on AWS would add substantial complexity around broker provisioning, storage sizing, partition planning, failover, upgrades, observability, and on-call burden. Kafka’s exactly-once semantics also do not eliminate the need for idempotent application logic when the side effect is sending email or invoking third-party webhooks. In other words, Kafka would impose significantly higher operational cost now while still requiring much of the same application correctness work for billing notifications.

If notification volume, retention needs, or broader event-driven architecture requirements materially grow beyond the current subsystem scope, Kafka should be revisited later. For the present constraints, Redis Streams is the better engineering decision.