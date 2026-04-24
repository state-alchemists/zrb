# ADR-001: Notification Subsystem Architecture

## Status

Proposed

## Context

The current notification system operates synchronously within the main application's HTTP request-response cycle. This has led to increased response latency, request timeouts during peak traffic, and cascading failures when downstream notification services (email, webhooks) are slow or unavailable. The system offers no delivery guarantees, which is a critical issue for billing-related notifications.

We need a new asynchronous architecture that can:
- Decouple notification processing from user-facing requests.
- Provide at-least-once delivery guarantees for general notifications and exactly-once semantics for critical billing events.
- Support retries with exponential backoff for failed deliveries.
- Scale to handle a projected 10x traffic increase without a major redesign.
- Be implemented and managed by a small engineering team of 6 with no dedicated infrastructure support and no prior experience with message brokers like Kafka.
- Leverage our existing Redis instance where possible to minimize operational overhead.

## Decision

We will use **Redis Streams** as the backbone of the new asynchronous notification subsystem.

The Flask application will produce a message to a Redis Stream for each notification event. This is a non-blocking, low-latency operation. A separate pool of worker processes will consume messages from the stream, handle the business logic of sending emails and webhooks, and manage retries.

This decision is based on Redis Streams providing the best balance of required technical capabilities against our severe operational constraints. It meets the core requirements of asynchronous processing, consumer groups for load balancing and retries, and sufficient throughput for our scaling targets, all while introducing minimal new operational complexity to our existing infrastructure.

## Consequences

### Pros:

- **Low Operational Overhead**: We already run and manage Redis in production. Adopting Streams requires no new infrastructure, monitoring, or specialized knowledge, which is critical for our small team.
- **Fast Implementation**: The team can leverage existing Redis knowledge and client libraries to deliver a working solution within the 2-week timeframe.
- **Sufficient Performance**: Redis is extremely fast and can easily handle the throughput required for our current and 10x scaling targets.
- **Meets Core Requirements**: Redis Streams provides persistence (AOF), consumer groups (enabling retries on a per-message basis), and a durable, append-only log structure suitable for a notification queue.

### Cons:

- **Weaker Exactly-Once Semantics**: Unlike Kafka's built-in transactional APIs, achieving exactly-once delivery with Redis Streams requires more careful application-level logic. We will need to enforce idempotency in our consumers by tracking message IDs to prevent duplicate processing, which adds a small amount of engineering complexity.
- **Limited Message Retention**: Message history is constrained by Redis memory, not disk space. This is acceptable for our notification use case, as we do not need long-term event replayability.
- **Smaller Ecosystem**: The ecosystem of tools and integrations for Redis Streams is less mature than Kafka's.

## Alternatives Considered

### Apache Kafka

Apache Kafka was seriously considered as it is the industry-standard solution for durable, high-throughput messaging.

- **Strengths**: Kafka offers superior durability, massive scalability, and robust, built-in support for exactly-once semantics, which was a strong draw for our billing notification requirement. Its message retention capabilities are also far more powerful.
- **Reason for Rejection**: The primary reason for rejecting Kafka is its **prohibitive operational complexity**. For a 6-person team with no prior Kafka experience and no dedicated operations engineer, the effort to correctly configure, deploy, monitor, and maintain a production-ready Kafka and Zookeeper/KRaft cluster would be immense. It would violate our constraint of delivering value within two weeks and would introduce significant risk of misconfiguration and downtime. The cost of a managed Kafka service at our target scale was also a budgetary concern. The operational simplicity of leveraging our existing Redis infrastructure was the deciding factor.
