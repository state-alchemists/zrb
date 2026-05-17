**Title**
ADR-001: Choose Redis Streams for the Notification Subsystem

**Status**
Proposed

**Context**
The current notification subsystem runs synchronously inside the Flask request cycle and is now causing production issues: elevated request latency, timeout spikes up to 8 seconds, silent notification loss when downstream providers fail, and cascading failures when slow webhook endpoints exhaust shared resources. The system must move to asynchronous processing with retries, exponential backoff, and dead-letter handling.

The platform currently serves about 85,000 monthly active users, processes roughly 2 million tasks per month, and sees peak traffic around 500 requests per second. The target is to support 10x growth without another architectural rewrite and to add WebSocket push notifications within two quarters.

The main constraints are organizational as much as technical. The team has 6 engineers, no dedicated infrastructure engineer, already operates Redis in production, has no Kafka experience, needs to deliver value within 2 weeks, and has a modest budget that rules out a fully managed Kafka deployment at meaningful scale. Billing-critical notifications require exactly-once behavior where feasible.

The decision is therefore not just about raw broker capability. It is about which option can satisfy the immediate reliability and delivery requirements with acceptable operational risk for a small team.

**Decision**
Choose Redis Streams as the messaging backbone for the notification subsystem.

Redis Streams is the better fit for the current system and team constraints. It provides the core capabilities this subsystem needs now: asynchronous decoupling from HTTP requests, ordered append-only streams, consumer groups for horizontal worker scaling, explicit acknowledgement, pending-entry tracking for retries, and retention controls. Because Redis is already part of the production stack, the team can deliver a working queue-based notification pipeline much faster than adopting Kafka from scratch.

This choice is driven primarily by operational complexity and time-to-value. Kafka offers higher throughput ceilings, stronger partition-based durability patterns, and a richer event-streaming ecosystem, but those advantages are not the bottleneck for this workload today. Even with 10x growth, the projected notification volume remains well within Redis Streams capacity for a single notification subsystem if stream design and retention are kept disciplined. The current peak of 500 requests per second is modest relative to both systems; the real problem is reliability and isolation, not broker saturation.

Ordering requirements also favor a simpler solution. Redis Streams preserve order within a stream, which is sufficient if notifications are partitioned by event type, tenant, or entity as needed. Kafka also preserves order only within a partition, so it does not create a meaningful advantage unless the system already needs broad multi-topic event replay at scale.

For delivery guarantees, Redis Streams natively provide at-least-once delivery through consumer groups and acknowledgements. Exactly-once delivery for billing notifications should not rely on the broker alone in either option. Kafka’s so-called exactly-once semantics are real but narrow: they apply to Kafka producer and stream-processing transactions, not end-to-end side effects such as sending an email, invoking a webhook, or calling a payment provider. Since the business requirement is exactly-once notification effects, the correct mechanism is idempotency at the application layer backed by PostgreSQL: persist an idempotency key or delivery record per billing event, only execute the external side effect once, and make retries safe. Redis Streams supports this pattern well enough.

In short: Redis Streams solves the production failure mode quickly, fits the existing infrastructure and team skill set, supports the needed retry and consumer-group model, and keeps operational burden low enough for a 6-person team.

**Consequences**
Pros:
- Low operational overhead because Redis is already deployed and understood by the team.
- Fastest path to production within the 2-week constraint.
- Sufficient throughput for current load and likely 10x near-term growth for the notification use case.
- Consumer groups provide horizontal scaling of notification workers.
- Pending-entry lists and acknowledgements support retries and recovery after worker failure.
- Stream ordering is straightforward within a stream and adequate for notification sequencing needs.
- Lower infrastructure cost than standing up and operating Kafka.
- Good fit for future WebSocket push notifications, since Redis is commonly used for low-latency fan-out patterns.

Cons:
- Weaker long-term event-streaming platform than Kafka for large-scale replay, analytics, and multi-team event integration.
- Retention is less robust as a system of record; Redis should not be treated as the durable source of truth for long historical event storage.
- Exactly-once semantics are not provided end-to-end by Redis; billing safety must be implemented explicitly in the application and database.
- Operational misuse is easier if the same Redis cluster continues to mix cache/session traffic with durable queue-like workloads; stream memory growth and eviction policy must be managed carefully.
- Retry scheduling with exponential backoff and dead-letter handling will require application logic rather than relying on a richer built-in broker ecosystem.

**Alternatives Considered**
Apache Kafka was rejected for now.

Kafka is technically stronger on several dimensions. It offers much higher throughput, durable log-based retention, strong consumer-group support, partition-based ordering, replayability, and producer/consumer patterns designed for large event-driven systems. If this company were building a broader event platform, had multiple downstream consumers, needed long-term retention and replay as a first-class requirement, or had an experienced platform team, Kafka would likely be the better strategic choice.

However, Kafka is the wrong choice under the current constraints. Its operational complexity is substantially higher than Redis Streams: brokers, partitions, replication configuration, monitoring, storage sizing, client tuning, and failure-mode management all impose overhead the current team is not staffed to absorb. The team has no Kafka experience, no dedicated infrastructure engineer, limited budget, and only 2 weeks to ship value. Running Kafka well in production is not trivial, and running it poorly would create a new reliability problem while trying to solve the current one.

Kafka’s exactly-once semantics also do not eliminate the hardest requirement here: exactly-once billing notifications as externally observed effects. Emails and webhooks still require idempotent application logic and persistent deduplication. That means Kafka’s strongest differentiator does not materially remove the need for a database-backed idempotency design in this subsystem.

For this notification subsystem, Kafka would be an overpowered but under-supported choice. It may become the right platform later if the company grows into organization-wide event streaming, but it is not the right decision now.
