# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context
The current notification system operates synchronously within the HTTP request cycle, leading to request timeouts (up to 8s), cascading failures due to slow third-party webhooks, and a lack of delivery guarantees for critical billing events. 

We need a solution that:
- Decouples notification logic from the request cycle.
- Supports retries with exponential backoff.
- Provides at-least-once delivery for most events and exactly-once semantics for billing.
- Scales to 10x current traffic (peak 5,000 req/s).
- Integrates with upcoming WebSocket push notifications.

**Constraints:**
- Team of 6 (no dedicated infra engineer).
- No existing Kafka experience.
- Redis is already running in production.
- Migration/setup must be completed within 2 weeks.
- Modest budget (cannot afford high-end managed Kafka services).

## Decision
We will use **Redis Streams** as the backbone for the notification subsystem.

**Justification:**
1. **Operational Simplicity**: We already operate Redis. Adding Streams requires no new infrastructure, no new monitoring stacks, and no new failure modes for the team to learn.
2. **Development Velocity**: The "2-week to value" constraint is high. Implementing a producer/consumer pattern on Redis Streams is trivial for a Python/Flask team, whereas Kafka involves a steep learning curve (Zookeeper/KRaft, partition management, offset tuning).
3. **Performance**: With a peak target of 5,000 req/s, Redis Streams' throughput is more than sufficient. The latency is lower than Kafka's, aiding the real-time WebSocket requirement.
4. **Consumer Groups**: Redis Streams provides Consumer Groups, allowing us to distribute notifications across multiple workers and track pending entries (PEL), which is essential for implementing the required retry logic and dead-letter queues.
5. **Exactly-Once Semantics**: While neither provides "magic" exactly-once delivery across network boundaries, we will achieve it for billing notifications by combining Redis's atomic operations with **idempotency keys** in our PostgreSQL database (e.g., `UNIQUE` constraint on `notification_id` and `event_type`).

## Consequences
### Pros
- **Zero Infrastructure Overhead**: No new clusters to manage or pay for.
- **Rapid Deployment**: Immediate start using existing client libraries.
- **Resource Efficiency**: Low memory/CPU footprint compared to a JVM-based Kafka cluster.
- **Alignment with Roadmap**: Redis is ideal for the subsequent WebSocket integration.

### Cons
- **Persistence Trade-off**: Redis is primarily in-memory. While AOF provides durability, it is not as robust as Kafka's distributed commit log. We mitigate this by treating the stream as a buffer and persisting final delivery states in PostgreSQL.
- **Lower Log Retention**: Redis Streams are typically pruned (XTRIM) to save memory, unlike Kafka which stores massive history. This is acceptable as notifications are transient events.

## Alternatives Considered
### Apache Kafka
Kafka was rejected for the following reasons:
- **Operational Complexity**: Managing a Kafka cluster (or even a small one) requires dedicated expertise we lack. The risk of misconfiguring partitions or replication factors would likely exceed the 2-week delivery window.
- **Over-Engineering**: Our peak throughput (5k req/s) does not justify the overhead of Kafka's distributed log architecture. Kafka is designed for millions of events per second; Redis is a better fit for our current scale.
- **Budget**: Managed Kafka (e.g., Confluent) is too expensive for our current stage. Self-hosting would consume too much of our 6-person team's bandwidth.
