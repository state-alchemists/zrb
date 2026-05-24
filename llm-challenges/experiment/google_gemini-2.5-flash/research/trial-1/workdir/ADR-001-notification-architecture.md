# ADR 001 — Notification Subsystem Architecture

- **Status**: Proposed
- **Date**: 2026-05-24
- **Deciders**: Engineering Team
- **Context tags**: notifications, asynchronous, message queue, Redis, Kafka

## Context

The existing notification module, part of a Python/Flask monolith, handles emails and webhooks synchronously within the HTTP request cycle. This approach has led to significant problems: request timeouts, silent failures due to external service outages, cascading failures from connection pool exhaustion, and a complete lack of delivery guarantees for critical notifications.

The current system serves 85,000 monthly active users and processes approximately 2 million tasks per month, with peak loads of 500 requests per second. We need to decouple notifications for asynchronous processing, implement retry mechanisms with exponential backoff, guarantee at-least-once delivery for all events, and support exactly-once delivery for billing-critical events. The new architecture must scale to 10x current traffic and accommodate real-time WebSocket push notifications within two quarters.

Our engineering team consists of 6 people (3 senior, 3 mid-level) with no dedicated infrastructure engineer. We currently use Redis for session storage and rate limiting. There is no prior team experience with Kafka. The solution must be implemented with a low budget, excluding fully managed Kafka solutions at scale, and deliver initial value within two weeks of setup.

## Decision

We will implement the notification subsystem using **Redis Streams**.

## Rationale

Redis Streams offers a compelling balance of advanced messaging features and operational simplicity, aligning well with our team's capabilities and constraints. Its stream data structure provides ordered, persistent logs with consumer groups, enabling at-least-once delivery and distributed consumption without complex coordination. The ability to leverage an existing Redis instance significantly reduces setup time and operational overhead. Redis Streams' XACK command allows for explicit acknowledgment, which, when combined with application-level idempotency, can achieve exactly-once processing for billing notifications. For our projected 10x traffic growth (5000 req/s), a well-tuned Redis cluster can handle the throughput for message ingestion, and the fan-out for WebSocket integration is well-supported by Redis's Pub/Sub capabilities, or by having consumer groups manage WebSocket delivery. The two-week delivery constraint is achievable given our team's existing familiarity with Redis and the relatively straightforward API of Redis Streams.

## Alternatives Considered

-   **Apache Kafka** — Kafka provides robust, high-throughput, fault-tolerant distributed logging with strong ordering guarantees and excellent scalability. Its native support for exactly-once semantics and long-term message retention are ideal for our scaling targets and delivery guarantees. However, adopting Kafka introduces significant operational complexity and a steep learning curve for our team, which has no prior Kafka experience and no dedicated infrastructure engineer. Setting up, configuring, and maintaining a self-managed Kafka cluster (or even a partial setup) within two weeks on a modest budget is not feasible, and managed Confluent Cloud at full scale is too expensive. The initial setup and migration effort would exceed our two-week delivery constraint, hindering our immediate need to decouple notifications and achieve delivery guarantees.

## Consequences

-   **Positive**:
    -   Leverages existing Redis infrastructure, reducing setup time and operational overhead.
    -   Lower learning curve for the engineering team due to prior Redis familiarity.
    -   Supports ordered messages, consumer groups, and message retention out-of-the-box.
    -   Achieves at-least-once delivery; exactly-once for critical paths is feasible with application-level idempotency.
    -   Provides a clear path for WebSocket integration using existing Redis capabilities.
    -   Meets the two-week setup/migration timeline for initial value delivery.
    -   Cost-effective, as it avoids expensive managed Kafka services.
-   **Negative**:
    -   Redis Streams' persistence model, while robust, is not designed for indefinite storage like Kafka. This will require a strategy for archiving or expiring old notification events if long-term historical access is needed beyond the stream's retention.
    -   Scaling Redis Streams for extreme throughput (beyond 10x current, into millions of messages per second consistently) might eventually require sharding and more complex cluster management than Kafka.
    -   Achieving true exactly-once semantics requires careful implementation of consumer-side idempotency, which adds application-level complexity compared to Kafka's more robust transactional guarantees.
-   **Follow-ups**:
    -   Investigate Redis clustering strategies for high availability and horizontal scaling.
    -   Define a message retention policy for Redis Streams.
    -   Design and implement idempotency patterns for critical billing notification consumers.
    -   Develop a plan for monitoring Redis Streams health and performance.
