Title
Redis Streams for the Notification Subsystem

Status
Proposed

Context
The current notification subsystem runs synchronously inside the Flask HTTP request cycle and is now a production risk. Notification delivery for emails and webhooks increases average request latency to 800 ms and can spike to 8 s during peak traffic. Failures are silent, there is no retry or dead-letter handling, and slow downstream webhook endpoints have already caused cascading failures by exhausting shared resources. The system must decouple notification work from request handling, add retries with exponential backoff, support real-time push notifications within two quarters, and sustain roughly 10x current load without another architectural rewrite.

The operating constraints are unusually important in this decision. The team is six engineers with no dedicated infrastructure specialist. They already run Redis in production, but have no Kafka experience. The first version must deliver value within two weeks, and the budget does not support a full managed Kafka offering such as Confluent Cloud at the expected future scale.

The notification workload is meaningful but not internet-scale. The platform serves 85,000 monthly active users, processes about 2 million tasks per month, and peaks around 500 requests per second. Even with 10x growth, the notification subsystem is still within the practical throughput envelope of Redis Streams if it is used as a focused work queue for notification fan-out rather than a company-wide event backbone.

A key constraint is delivery semantics for billing-critical notifications such as trial expiration and payment failure. Exactly-once delivery cannot be guaranteed purely by a broker in the end-to-end sense when external side effects are involved, especially for email and webhooks. Any acceptable design must therefore combine broker guarantees with idempotent application logic, durable event IDs, deduplication, and transactional state management in PostgreSQL.

Decision
Choose Redis Streams as the notification backbone for the next-generation notification subsystem.

This is the better fit because it solves the current production problem within the team’s operational and time constraints. Redis Streams provides an append-only log with consumer groups, pending-entry tracking, explicit acknowledgements, replay of unacknowledged messages, and enough throughput for the current workload and near-term 10x target. It lets the team build asynchronous workers quickly using infrastructure they already operate, which materially reduces migration risk and time to value.

Kafka is stronger on raw throughput, long retention, partitioned durability, and mature stream processing semantics. It also offers stronger ordering guarantees within partitions and supports exactly-once semantics for Kafka-to-Kafka processing. However, those advantages do not outweigh the operational burden here. Kafka would introduce ZooKeeper-less KRaft cluster operations, broker sizing, partition management, monitoring, storage planning, client tuning, and incident response patterns the team does not currently know. For a six-person team without infra ownership and with a two-week delivery window, that complexity is the wrong trade.

Redis Streams is sufficient on the technical properties that matter most now:
- Throughput: easily adequate for current traffic and the projected 10x growth of a notification queue workload, assuming messages are lightweight and workers scale horizontally.
- Ordering: stream order is preserved, and per-consumer-group processing can be designed to preserve per-entity ordering where needed. Global strict ordering is not a requirement for notifications.
- Message retention: configurable and adequate for operational replay windows, retries, and dead-letter handling, even though it is not as strong or as cheap for long-term retention as Kafka.
- Consumer groups: supported natively, including claiming pending messages from failed workers.
- Delivery semantics: at-least-once delivery is straightforward. “Exactly-once” for billing should be implemented end-to-end via idempotency keys, a transactional outbox in PostgreSQL, and provider-side deduplication where available, not delegated to the broker.
- Operational complexity: materially lower than Kafka because Redis is already in production and familiar to the team.

The implementation should treat Redis Streams as the transport layer, not the source of truth. Billing notifications should be produced via a PostgreSQL-backed outbox table in the same transaction as the business event, then published to Redis Streams by a relay worker. Consumers must record processed event IDs and enforce idempotency before sending emails or webhooks. This is the practical way to satisfy the exactly-once requirement “where feasible” for a system with external side effects.

Consequences
Pros:
- Fastest path to removing notification work from the request cycle and reducing latency and timeout risk.
- Lower operational complexity because the team already runs Redis and does not need to learn or operate Kafka immediately.
- Consumer groups and pending-entry recovery provide a solid basis for retries, worker failover, and dead-letter processing.
- Good enough throughput for the current system and plausible 10x growth in a dedicated notification pipeline.
- Lower upfront infrastructure cost than introducing Kafka.
- Fits well with planned WebSocket push notifications, where Redis-based fan-out and lightweight event delivery are often a pragmatic choice.

Cons:
- Weaker long-term retention and replay model than Kafka; Redis is not ideal as a durable event history for large-scale analytics or broad event-driven integration.
- Exactly-once semantics are not provided by Redis Streams for external side effects; the application must implement idempotency and transactional outbox patterns correctly.
- Ordering guarantees are weaker than Kafka’s partition-based model for large distributed consumers; preserving strict per-entity order may require careful keying and worker design.
- Redis memory usage and retention management must be monitored closely as stream volume grows.
- If the platform later evolves into a larger event-driven architecture with many independent downstream consumers and long replay windows, Redis Streams may become a transitional solution rather than the final platform.

Alternatives Considered
Apache Kafka was rejected for this phase.

Kafka is the more powerful event platform. It offers very high throughput, durable disk-backed retention, strong partition-based ordering, mature consumer group behavior, and exactly-once semantics for specific processing patterns inside the Kafka ecosystem. If the primary problem were building a long-lived event backbone across many services, Kafka would be a serious contender.

It is not the right choice under the stated constraints. The team has no Kafka experience, no dedicated infrastructure engineer, only a two-week window before value must be delivered, and limited budget for managed service adoption. Self-managing Kafka on AWS would introduce substantial operational complexity and failure modes at exactly the moment the system needs a fast, low-risk stabilization of notification delivery. Its exactly-once guarantees also would not eliminate the need for application-level idempotency when calling external email and webhook providers, so the hardest part of the billing requirement would still remain.

For this system, Kafka is better viewed as a future migration option if notification traffic grows far beyond the projected 10x target or if the company later standardizes on an event-streaming architecture across multiple services. Today, it is more system than the problem and the team can responsibly absorb.