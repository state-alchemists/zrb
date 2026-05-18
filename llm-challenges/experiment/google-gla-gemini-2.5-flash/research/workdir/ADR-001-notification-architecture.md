# ADR 001 — Asynchronous Notification Subsystem

- **Status**: Proposed
- **Date**: 2026-05-18
- **Deciders**: Zrb (LLM Agent)
- **Context tags**: notifications, asynchronous, messaging, reliability, scalability

## Context

The current synchronous notification system in our Python/Flask monolith causes significant issues: request timeouts (avg 800ms, spikes to 8s), silent failures without retry, cascading failures due to slow external webhook endpoints, and a lack of delivery guarantees for critical notifications.

Our scaling targets require decoupling notifications for async processing, supporting retry with exponential backoff, guaranteeing at-least-once delivery (and exactly-once where feasible, especially for billing events), supporting 10x traffic growth, and enabling real-time WebSocket push notifications within two quarters.

Key constraints include: a small engineering team (6 people, no dedicated infra), existing Redis in production, no prior Kafka experience, a strict 2-week setup/migration timeline, a modest budget (precluding managed Confluent Cloud), and the critical need for exactly-once semantics for billing notifications.

## Decision

We will use **Redis Streams** for our asynchronous notification subsystem.

## Rationale

Redis Streams is chosen primarily due to its low operational overhead and the team's existing familiarity with Redis. The team already operates Redis in production for caching and rate limiting, reducing the learning curve and time to value significantly. This directly addresses the constraint of "no dedicated infrastructure engineer" and the "2 weeks setup/migration" limit.

While Kafka offers superior high-throughput capabilities and a richer ecosystem for complex streaming, the current peak of ~500 req/s with 2M tasks/month is well within Redis Streams' capacity, especially when scaling Redis horizontally if needed. For billing notifications, Redis Streams' consumer group mechanism, coupled with application-level idempotency, can achieve exactly-once processing (or at least-once with idempotent consumers, which is a strong pattern for exactly-once). The ability to add real-time WebSocket push notifications within two quarters also aligns well with Redis' pub/sub capabilities, which can be integrated with Streams. The modest budget constraint also favors leveraging existing infrastructure over investing in a new, potentially expensive, managed Kafka service.

## Alternatives Considered

-   **Apache Kafka**: Kafka was rejected primarily due to the "no Kafka experience on the team today" and "no dedicated infrastructure engineer" constraints. While Kafka excels in high-throughput, long-term message retention, and robust consumer group features, the steep learning curve for deployment, operation, and troubleshooting a new distributed system would significantly exceed the "2 weeks setup/migration" timeframe and strain the small engineering team. The modest budget also precludes readily available managed Kafka solutions like Confluent Cloud that would alleviate some operational burden. The benefits of Kafka's ecosystem, while significant, do not outweigh the immediate operational and learning cost for our current team and scale. Achieving exactly-once semantics with Kafka requires careful implementation of consumer offsets and idempotent producers, which would also add complexity for a team new to the technology.

## Consequences

-   **Positive**:
    -   Leverages existing Redis infrastructure and team knowledge, reducing setup time and operational burden.
    -   Immediately addresses request timeouts and enables asynchronous processing.
    -   Provides retry mechanisms and delivery guarantees (at-least-once, with exactly-once achievable via idempotent consumers for critical events).
    -   Supports future real-time WebSocket push notifications effectively.
    -   Meets current scaling needs and provides headroom for 10x growth with horizontal scaling of Redis.
-   **Negative**:
    -   While scalable, Redis Streams may not offer the extreme throughput or long-term arbitrary message retention of Kafka for future, unforeseen ultra-high-scale scenarios or complex data lake integrations without additional architecture.
    -   Monitoring and advanced stream analytics features are not as mature or out-of-the-box compared to Kafka's ecosystem, requiring more custom development.
    -   Scaling Redis for high availability and persistence, especially for Streams, will require careful planning (e.g., Redis Cluster or Sentinel) as traffic grows, adding some operational complexity compared to simple Redis caching.
-   **Follow-ups**:
    -   Implement producer-side logic to add notification events to Redis Streams.
    -   Develop a new microservice or worker pool (e.g., Celery) to consume from Redis Streams and send notifications.
    -   Design and implement idempotent consumers for billing-critical events.
    -   Establish monitoring and alerting for Redis Stream backlog and consumer group health.
    -   Document Redis Stream usage patterns and operational best practices for the team.

## Backlinks

- [ADR index](index.md)
