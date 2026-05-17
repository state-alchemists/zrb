**Title**

ADR-001: Use Redis Streams for the notification subsystem

**Status**

Proposed

**Context**

The current notification subsystem runs synchronously inside the Flask HTTP request cycle. This is causing high request latency, request timeouts, silent notification loss when downstream providers fail, and cascading failures when slow webhook endpoints exhaust shared resources. The platform currently serves about 85,000 monthly active users, processes roughly 2 million tasks per month, and sees peak traffic around 500 requests per second. The business expects 10x growth and wants to add real-time WebSocket notifications within two quarters.

The replacement architecture must decouple notification delivery from user-facing requests, support retries with exponential backoff, and provide at-least-once delivery for general notifications. Billing-critical notifications require exactly-once semantics where feasible. The team is small: 6 engineers with no dedicated infrastructure engineer and no Kafka operating experience. The organization already runs Redis in production for sessions and rate limiting, has a modest budget, and needs to deliver value within two weeks rather than spending a cycle building platform expertise.

The two options under consideration are Apache Kafka and Redis Streams.

**Decision**

Choose Redis Streams as the messaging backbone for the notification subsystem.

This decision is primarily driven by operational fit and time-to-value. Redis Streams provides the core capabilities this system needs now: asynchronous message handling, consumer groups for horizontal workers, ordered consumption within a stream, message retention controls, pending-entry tracking, and replay for failed consumers. Because Redis is already in production, adopting Streams is an incremental extension of existing infrastructure rather than introducing an entirely new distributed system.

Redis Streams is sufficient for the expected scale. Even with 10x growth from the current workload, the notification volume implied by a 500 req/s peak SaaS application is well within Redis Streams’ practical throughput envelope for a single notification subsystem, especially compared with the much larger scale Kafka is typically chosen for. Consumer groups allow multiple workers to process notifications in parallel while preserving per-stream ordering characteristics. For email, webhook, and future WebSocket fan-out workloads, this is adequate.

Kafka is technically stronger in raw throughput, partitioned scalability, long-term retention, and mature exactly-once stream-processing semantics. However, those strengths come with materially higher operational complexity: brokers, partitions, replication, retention sizing, consumer lag monitoring, rebalancing behavior, schema governance, and a steeper failure model. Given the team has no Kafka experience, no dedicated infrastructure engineer, and a two-week delivery constraint, Kafka would add significant execution risk and likely delay the actual fix to the current production problem.

For exactly-once billing notifications, neither Kafka nor Redis Streams alone should be treated as a complete business-level exactly-once guarantee. Exactly-once semantics at the application boundary still require idempotent consumers and a durable deduplication strategy. With Redis Streams, we should implement transactional persistence of billing notification intent in PostgreSQL, assign an idempotency key per billing event, and have workers record successful delivery outcomes before acknowledging the stream entry. This gives effectively exactly-once business behavior using the database the system already trusts, without depending on Kafka’s more complex transactional model.

In short, Redis Streams best matches the current system constraints: it solves the immediate reliability and latency problems, supports retries and worker scaling, is fast enough for projected growth, and can be introduced by this team within the required timeline.

**Consequences**

Pros:
- Lower operational complexity than Kafka, which matters because the team has no Kafka expertise and no dedicated infrastructure owner.
- Faster setup and migration because Redis already exists in production; this makes the two-week delivery target realistic.
- Supports asynchronous processing, consumer groups, pending message recovery, replay, and bounded retention, which directly addresses the current notification failures.
- Good enough throughput for current load and likely 10x growth for a notification workload of this size.
- Simplifies future addition of WebSocket notifications because the same stream-based pipeline can feed push workers.
- Lower infrastructure cost than standing up a production-grade Kafka cluster.
- Easier to operate and debug for a small engineering team.

Cons:
- Weaker native exactly-once semantics than Kafka; exactly-once billing behavior must be implemented at the application level with idempotency and durable deduplication.
- Less suitable than Kafka for very high sustained throughput or broad event-stream reuse across many independent downstream systems.
- Ordering guarantees are simpler but also more limited; strict global ordering is not realistic once work is parallelized across consumers.
- Message retention is more operationally constrained than Kafka’s log-based model and is generally better suited to shorter-lived queues than long-lived event history.
- Redis persistence and memory sizing must be managed carefully so the notification workload does not interfere with existing session and rate-limiting usage.

**Alternatives Considered**

Apache Kafka was rejected for now.

Kafka offers higher throughput, durable log-based retention, strong partition ordering, consumer groups at large scale, replay over long windows, and mature exactly-once semantics for specific producer/consumer patterns. If this were a larger platform team building a company-wide event backbone, Kafka would be a strong candidate.

However, Kafka is the wrong choice under the current constraints. The team does not operate Kafka today, has no in-house Kafka experience, lacks a dedicated infrastructure engineer, and must deliver value within two weeks. A production-ready Kafka deployment requires substantially more setup and operational discipline than Redis Streams. It also introduces higher ongoing cost and cognitive load. Most importantly, Kafka’s exactly-once semantics would still not remove the need for idempotent handling when sending emails or calling third-party webhooks, so its headline guarantee does not fully solve the billing requirement by itself.

Given the current scale, team size, budget, and urgency, Kafka would be overpowered but underfit. Redis Streams solves the immediate problem with less risk and a much higher probability of successful adoption.