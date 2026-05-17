# ADR-001: Notification Subsystem Architecture

## Status

Proposed

## Context

The current notification system operates synchronously within the HTTP request cycle. This architecture has led to increased request latency, cascading failures due to slow downstream services (webhooks, email providers), and silent data loss when those services are unavailable. There are no delivery guarantees, which is a critical issue for billing-related events that require exactly-once processing.

The new system must decouple notification processing from web requests, handle a 10x increase in traffic, support retries, and provide at-least-once delivery guarantees for general notifications and exactly-once semantics for critical billing notifications.

This decision is constrained by a small engineering team (6 people) with no dedicated infrastructure support, no prior experience with Apache Kafka, and a requirement to deliver value within a two-week timeframe. The team already operates and is familiar with Redis.

## Decision

We will use **Redis Streams** as the backbone for the new asynchronous notification subsystem.

A single stream, `notification_events`, will be used. Events will be produced by the Flask backend and consumed by one or more dedicated worker services. We will utilize Redis Consumer Groups to allow multiple workers to process the stream in parallel, ensuring scalability and fault tolerance.

- **For at-least-once delivery** (e.g., task updates), consumers will acknowledge messages (`XACK`) after successfully processing them. In case of worker failure before acknowledgement, the message will be redelivered to another consumer.
- **For exactly-once semantics** (e.g., billing events), we will implement idempotency at the consumer level. A consumer will store the ID of each processed billing message in a separate Redis Set with a TTL. Before processing a new message, the consumer will check for the message ID's existence in this set. This check-and-set operation prevents duplicate processing in the event of a redelivery.

This approach leverages our existing Redis infrastructure and operational knowledge, minimizing the introduction of new, complex systems.

## Consequences

### Pros:
- **Low Operational Overhead**: Utilizes the existing Redis instance, which the team is already proficient in managing, monitoring, and scaling. This avoids the significant learning curve and operational burden of introducing and maintaining a new distributed system like Kafka.
- **Rapid Implementation**: The team can leverage existing Redis expertise and client libraries to meet the two-week deadline for delivering initial value.
- **Meets Performance Requirements**: Redis Streams can comfortably handle the projected 10x traffic growth (~5000 events/s) without being over-engineered for the current scale.
- **Achieves Delivery Guarantees**: The combination of consumer groups, acknowledgements, and application-level idempotency checks fulfills the at-least-once and exactly-once delivery requirements.

### Cons:
- **Limited Message Retention**: Redis is primarily an in-memory store. While persistence is available (AOF/RDB), it is not a durable, disk-first log like Kafka. A catastrophic Redis failure could lead to data loss of in-flight messages. This risk is acceptable for non-critical notifications, and mitigated for billing events by the idempotent consumer logic.
- **Weaker Ecosystem**: The tooling and ecosystem around Redis Streams for stream processing is less mature than Kafka's.
- **Application-Level Complexity**: The logic for ensuring exactly-once semantics resides in our application code, not the infrastructure. This requires careful implementation and testing.

## Alternatives Considered

### Apache Kafka

Apache Kafka was seriously considered as it is the industry standard for durable, high-throughput message queues.

- **Technical Fit**: Kafka provides powerful features like persistent log storage, high throughput, and native support for exactly-once semantics, making it an excellent technical fit for the problem.
- **Reason for Rejection**: We rejected Kafka primarily due to **high operational complexity**. For a small team with no prior Kafka or Zookeeper/KRaft experience, the effort to provision, configure, secure, monitor, and maintain a production-grade Kafka cluster would far exceed the two-week setup constraint and introduce significant ongoing operational risk. The cost of a suitable managed Kafka service was also considered prohibitive under current budget constraints. The learning curve required to correctly implement Kafka's exactly-once features would also jeopardize the project timeline.
