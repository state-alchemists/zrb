# ADR 001 — Notification Subsystem Architecture

- **Status**: Proposed
- **Date**: 2026-05-17
- **Deciders**: Zrb
- **Context tags**: notifications, async, messaging, architecture, scaling

## Context

The current notification module in our SaaS project management platform is handled synchronously within the HTTP request cycle. This has led to request timeouts, silent failures, cascading system failures due to slow external endpoints, and a lack of delivery guarantees for critical notifications. The system needs to decouple notifications, support retries with exponential backoff, guarantee at-least-once delivery for billing events (and exactly-once where feasible), and prepare for real-time WebSocket push notifications within two quarters, while handling 10x traffic growth.

Key constraints include an engineering team of 6 with no dedicated infrastructure engineer, existing Redis in production, no current Kafka experience, a maximum of two weeks for initial setup/migration, a modest budget (precluding full-scale managed Confluent Cloud), and the necessity of exactly-once semantics for billing notifications.

## Decision

We will use Redis Streams for the notification subsystem.

This decision leverages our existing Redis infrastructure and team familiarity, offering a lower operational overhead and faster time-to-value compared to introducing a new technology stack like Kafka. Redis Streams provide the necessary functionalities for asynchronous processing, consumer groups, message retention, and can support at-least-once delivery and, with careful implementation, exactly-once processing for critical messages.

## Rationale

Redis Streams are chosen primarily due to the steep learning curve for our team, lack of existing Kafka experience, and the associated operational complexity and cost. While Kafka offers superior throughput and stronger native support for exactly-once semantics at massive scale, our current traffic (500 req/s peak) and projected 10x growth are within Redis Streams' capabilities. The constraint of "not require more than 2 weeks of setup/migration work before delivering value" and a "modest budget" made Kafka a less viable immediate choice. Introducing a new distributed system like Kafka would likely exceed the setup/migration timeframe and require a significant upfront investment in learning and infrastructure management, which our 6-person team without a dedicated infrastructure engineer cannot easily absorb.

Redis Streams offer key features required:

-   **Asynchronous processing**: Messages can be pushed to a stream and processed by separate workers, immediately decoupling notifications from the HTTP request cycle.
-   **Consumer Groups**: Redis Streams natively support consumer groups, allowing multiple consumers to process a stream concurrently, distributing the load and providing a robust mechanism for retry and failure handling. This is crucial for implementing exponential backoff and preventing silent failures.
-   **Message Retention**: Configurable message retention allows for historical data and re-processing in case of consumer failures.
-   **At-least-once delivery**: With ACK mechanisms and consumer groups, Redis Streams guarantee at-least-once delivery, which can be extended to exactly-once semantics for billing notifications by implementing idempotent consumers.
-   **Operational Complexity**: Given no dedicated infrastructure engineer and a limited team size, the operational complexity of managing Redis Streams is significantly lower than a self-hosted Kafka cluster. It also avoids the cost of managed Kafka services like Confluent Cloud.
-   **Scalability**: While Kafka is generally more scalable for extremely high throughput, Redis Streams can comfortably handle the current 500 req/s peak and 10x projected growth, especially within our immediate budget and operational constraints. Its simplicity allows for faster iteration and delivery of value within the 2-week timeframe.
-   **Real-time Push Notifications**: Redis's pub/sub capabilities, combined with Streams, make it a natural fit for building out WebSocket push notifications within the two-quarter target, consolidating messaging infrastructure.

## Alternatives Considered

-   **Apache Kafka** — This option was rejected primarily due to the steep learning curve for our team, lack of existing Kafka experience, and the associated operational complexity and cost. While Kafka offers superior throughput and stronger native support for exactly-once semantics at massive scale, our current traffic (500 req/s peak) and projected 10x growth are within Redis Streams' capabilities. The constraint of "not require more than 2 weeks of setup/migration work before delivering value" and a "modest budget" made Kafka a less viable immediate choice. Introducing a new distributed system like Kafka would likely exceed the setup/migration timeframe and require a significant upfront investment in learning and infrastructure management, which our 6-person team without a dedicated infrastructure engineer cannot easily absorb.

## Consequences

What this decision *commits us to* and what it *closes off*.

-   **Positive**:
    -   Reduced request timeouts and improved API response times by decoupling notification processing.
    -   Increased reliability and reduced silent failures through robust retry mechanisms and consumer groups.
    -   Improved system stability by isolating notification failures and preventing cascading issues.
    -   Cost-effective solution by leveraging existing Redis infrastructure and team knowledge.
    -   Faster implementation and time-to-value within the 2-week constraint.
    -   A unified messaging platform that can easily extend to real-time WebSocket push notifications.
    -   At-least-once delivery guaranteed, with a clear path to exactly-once for billing-critical events.

-   **Negative**:
    -   While scalable for our current and projected needs, Redis Streams may eventually hit scaling limits (e.g., extremely high throughput, very long message retention for audit logs, complex data transformations) that Kafka would handle more gracefully. This might necessitate a migration to Kafka or a more robust message broker in the distant future if traffic exceeds a certain threshold, but not within the 10x growth target.
    -   Implementing exactly-once semantics requires careful design of idempotent consumers, which adds development complexity compared to Kafka's native support for this at the broker level.

-   **Follow-ups**:
    -   Design and implement idempotent consumers for billing-critical notifications.
    -   Develop a monitoring strategy for Redis Streams consumer groups and message backlogs.
    -   Document operational runbooks for Redis Streams.
    -   Investigate and benchmark Redis Streams performance under simulated 10x load.
