# ADR-001: Notification Subsystem Architecture

## Status

Proposed

## Context

The current notification system operates synchronously within the HTTP request cycle. This architecture has led to increased response latency, request timeouts, and cascading failures when downstream services (email providers, webhooks) are slow or unavailable. Critical notifications, such as for billing, lack delivery guarantees, posing a business risk.

The new system must decouple notification processing from API requests, support retries with exponential backoff, provide at-least-once delivery guarantees (and exactly-once for billing events), and be capable of handling 10x traffic growth.

The decision is constrained by a small engineering team (6 people) with no dedicated infrastructure engineer, no prior experience with Apache Kafka, an existing production Redis instance, and a requirement to deliver value within two weeks.

## Decision

We will use **Redis Streams** as the backbone of the new asynchronous notification subsystem.

The Flask backend will act as a producer, creating a new entry in a Redis Stream for each notification event. This is a fast, non-blocking operation. A separate pool of worker processes will act as consumers, using a consumer group to read from the stream, process notifications (send emails, webhooks), and acknowledge messages upon successful delivery.

This choice directly addresses the primary constraints:
1.  **Operational Simplicity**: We already run and manage Redis. Using Streams adds minimal operational overhead compared to deploying, managing, and learning a new, complex distributed system like Kafka.
2.  **Team Experience**: The team is familiar with Redis, significantly reducing the learning curve and implementation time. This allows us to meet the two-week deadline.
3.  **Required Guarantees**: Redis Streams with consumer groups and explicit acknowledgements (`XACK`) provides the at-least-once delivery guarantee required for most notifications. Exactly-once semantics for critical billing events will be achieved at the application layer through idempotent consumers (e.g., storing a unique message ID to prevent duplicate processing).

## Consequences

### Pros

-   **Low Operational Overhead**: Leverages our existing Redis infrastructure and expertise.
-   **Fast Time-to-Market**: The team's familiarity with Redis enables a rapid implementation that fits within the two-week constraint.
-   **Sufficient Performance**: Redis Streams can comfortably handle the projected 10x traffic increase (~5000 events/sec), especially for the relatively small message payloads of notifications.
-   **Decoupling**: Immediately solves the core problem of synchronous processing, improving API response times and system resilience.

### Cons

-   **Weaker Durability than Kafka**: Redis is primarily an in-memory system. While persistence (AOF) provides good durability, it is not as robust as Kafka's disk-based, replicated log. A catastrophic Redis failure could result in the loss of unacknowledged messages.
-   **Application-Layer Exactly-Once**: Redis does not offer built-in exactly-once semantics. This logic must be built into our consumer applications, which adds a degree of complexity.
-   **Limited Message Retention**: Message history is constrained by available RAM, unlike Kafka which is designed for long-term retention on disk. This is acceptable as we do not have a requirement to "replay" events from months ago.

## Alternatives Considered

### Apache Kafka

Apache Kafka was rejected primarily due to its significant operational complexity. For a team of our size with no dedicated infrastructure support and no prior Kafka experience, self-hosting Kafka (and its Zookeeper/KRaft dependency) would be a major undertaking. The learning curve, tuning, and ongoing maintenance would violate our two-week delivery constraint and introduce substantial risk. While managed services exist, they were deemed outside our modest budget.

While Kafka offers superior durability, longer message retention, and built-in support for exactly-once semantics, these powerful features represent over-engineering for our immediate needs. The operational cost and risk associated with Kafka outweigh its technical benefits in our current context. Redis Streams provides a "good enough" solution that solves our immediate problems pragmatically and allows us to deliver value quickly.
