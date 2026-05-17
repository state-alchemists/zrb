# ADR 001 — Notification Subsystem Architecture

- **Status**: Proposed
- **Date**: 2026-05-17
- **Deciders**: Engineering Team
- **Context tags**: notifications, message-queue, scalability, reliability

## Context

The current synchronous notification system in our Python/Flask monolith is failing under load. 
- **Latency**: HTTP responses are blocked by email/webhook delivery, causing spikes up to 8 seconds.
- **Reliability**: No retry mechanism or Dead Letter Queue (DLQ) leads to silent failures.
- **Stability**: Slow external endpoints cause connection pool exhaustion, leading to cascading failures.

We need a decoupled, asynchronous system that can handle 500 req/s today and 5,000 req/s (10x growth) in the future. We must support at-least-once delivery for billing events and sub-second latency for future WebSocket push notifications.

**Constraints**:
- Small team (6 engineers) with no dedicated infrastructure or Kafka experience.
- Redis is already running in production for session management and rate limiting.
- Tight timeline: < 2 weeks to deliver value.
- Modest budget for new infrastructure.

## Decision

We will use **Redis Streams** as the primary message broker for the notification subsystem.

> We will implement Redis Streams using consumer groups for horizontal scaling and the Pending Entry List (PEL) to ensure reliable message processing and at-least-once delivery.

## Rationale

Redis Streams is the optimal choice for our specific constraints:
1. **Operational Simplicity**: We already run and monitor Redis. Adding Streams requires zero new infrastructure setup, fitting our 2-week delivery window.
2. **High Throughput / Low Latency**: Redis easily handles 5,000 req/s on a single instance with sub-millisecond latency. This exceeds our 10x growth target and provides the low-latency foundation needed for the Q3 WebSocket roadmap.
3. **Reliability Features**: Redis Streams' consumer groups provide built-in message acknowledgment and the ability to claim "stuck" messages (via `XPENDING` and `XCLAIM`), satisfying at-least-once delivery requirements for billing.
4. **Team Capability**: The 6-person team can leverage existing Redis knowledge. The learning curve for the `XADD`/`XREADGROUP` API is significantly lower than Kafka's configuration and partition management.
5. **Budget**: Zero additional infrastructure cost at our current scale compared to the high overhead or service fees of a Kafka deployment.

## Alternatives Considered

- **Apache Kafka**: Rejected. While Kafka offers superior durability and native exactly-once semantics, its operational complexity (Zookeeper/KRaft, JVM tuning, partition strategies) is too high for a 6-person team with no prior experience. Setting it up reliably would exceed our 2-week deadline and incur significant management overhead.
- **PostgreSQL (as a queue)**: Rejected. While convenient, the table-as-queue pattern would increase bloat on our single primary DB and would not scale effectively to the 5,000 req/s target without impacting core application performance.

## Consequences

- **Positive**: Immediate decoupling of HTTP cycles; rapid implementation; unified infrastructure footprint.
- **Negative**: **Memory Management**: Unlike Kafka (disk-based), Redis is in-memory. We must implement stream trimming (`MAXLEN` or `MINID`) to prevent OOM.
- **Negative**: **Durability Trade-off**: We must ensure Redis AOF (Append Only File) is configured with `fsync everysec` (or `always` for billing-specific streams) to minimize data loss risk during crashes.
- **Follow-ups**:
    - Implement the **Idempotent Consumer** pattern (using task IDs in Postgres/Redis) to achieve effective exactly-once semantics for billing notifications.
    - Setup monitoring for Redis memory usage and Stream consumer lag.
    - Define a stream-trimming policy (e.g., keep last 100k messages).

## Backlinks

- [System Context](system_context.md)
