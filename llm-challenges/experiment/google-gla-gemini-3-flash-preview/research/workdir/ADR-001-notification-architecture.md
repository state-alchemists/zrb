# ADR-001: Notification Architecture Decision

## Status
Proposed

## Context
Our current notification system is synchronous, causing request timeouts (up to 8s) and cascading failures due to blocking I/O in the Flask monolith. We lack a retry mechanism and delivery guarantees for billing-critical events.

### Constraints & Requirements
- **Team**: 6 engineers, no dedicated DevOps/Infra.
- **Timeline**: Must deliver value in < 2 weeks.
- **Budget**: Modest; preference for existing infrastructure.
- **Scale**: Current 500 req/s, target 5,000 req/s (10x growth).
- **Guarantees**: Exactly-once for billing; at-least-once for general notifications.

## Decision
We will use **Redis Streams** to power the notification subsystem.

### Justification
1. **Operational Simplicity**: We already operate Redis in production for sessions and rate limiting. Adding Streams introduces zero new infrastructure overhead, whereas Kafka requires managing Zookeeper/KRaft and complex JVM tuning.
2. **Time-to-Market**: Given the 2-week constraint and the team's lack of Kafka experience, Redis Streams allows us to leverage existing Python libraries (`redis-py`) immediately.
3. **Throughput**: At 5,000 req/s (our 10x target), Redis (in-memory) provides more than enough headroom. Kafka’s disk-based persistence is unnecessary for this volume.
4. **Reliability**: Redis Consumer Groups provide the necessary "Pending Entries List" (PEL) to track unacknowledged messages, enabling at-least-once delivery and retries.
5. **Pragmatic Exactly-Once**: While Kafka offers native transactional producers, we can achieve exactly-once for billing by combining Redis Streams with **Idempotency Keys** in our PostgreSQL database—a pattern the team can implement without a steep learning curve.

## Consequences
### Pros
- **Low Latency**: In-memory message brokering keeps notification enqueueing < 1ms.
- **Unified Stack**: Simplifies monitoring and local development.
- **WebSocket Ready**: Redis Pub/Sub (complementary to Streams) is the industry standard for the WebSocket push requirements planned for Q3.
- **Cost Effective**: No additional licensing or managed service costs for Confluent/MSK.

### Cons
- **Memory Constraints**: Unlike Kafka, which stores data on disk, Redis Streams are limited by RAM. We must implement strict `MAXLEN` capping on streams to prevent OOM (Out of Memory) errors.
- **Durability**: Redis persistence (AOF/RDB) is less robust than Kafka's commit log. A catastrophic Redis failure could result in small data loss if not configured for `fsync` on every command (which impacts performance).
- **Manual Backoff**: Redis Streams does not natively support "retry after X minutes." We will need to implement a "delayed retry" logic using Redis Sorted Sets or a secondary "retry stream."

## Alternatives Considered
### Apache Kafka
**Rejected** due to:
- **High Complexity**: The learning curve for a 6-person team to manage partitioning, offsets, and replication factors is too steep for a 2-week window.
- **Overkill**: Kafka is designed for gigabytes per second; our peak load is well within Redis's single-node capabilities.
- **Cost**: Managed Kafka services (AWS MSK or Confluent) significantly exceed our current modest budget.
