# ADR-001: Notification Subsystem Architecture

## Title
ADR-001: Selection of Redis Streams for Async Notification Processing

## Status
Proposed

## Context
Our current notification system is synchronous, leading to 8s latency spikes, silent failures, and cascading connection pool exhaustion. We need to decouple this into an asynchronous process.

**Constraints:**
- **Team:** 6 engineers, no dedicated infra/SRE, no existing Kafka experience.
- **Timeline:** Must deliver value within 2 weeks.
- **Budget:** Modest; managed Kafka (Confluent) is currently cost-prohibitive.
- **Current Stack:** Python/Flask, PostgreSQL, and Redis (already in production for sessions).
- **Scale:** ~500 req/s peak, needing to support 5,000 req/s (10x growth).
- **Requirements:** At-least-once delivery for general notifications, exactly-once semantics (EOS) for billing, and support for WebSockets.

## Decision
We will use **Redis Streams** as the backbone for the notification subsystem.

### Justification
1. **Operational Familiarity:** The team already operates Redis in production. Adding Streams introduces zero new infrastructure overhead, whereas Kafka requires managing ZooKeeper/KRaft and JVM tuning, for which the team has no expertise.
2. **Implementation Speed:** Given the 2-week constraint, Redis Streams' simple API and existing Python client support (redis-py) allow for immediate development. Kafka would require a significant learning curve and complex configuration to reach production readiness.
3. **Performance/Scale:** At our 10x growth target (5,000 req/s), Redis remains highly performant with sub-millisecond latency. Kafka's massive throughput capabilities are not required for our current or near-future scale.
4. **Exactly-Once Semantics:** While Kafka offers native transactions for EOS, we can achieve effective exactly-once delivery for billing by using the **Transactional Outbox Pattern** in PostgreSQL combined with idempotent consumers (using message IDs as idempotency keys in Postgres). This is a more robust pattern for a small team than configuring Kafka's EOS correctly.
5. **WebSocket Compatibility:** Redis's Pub/Sub and Streams integrate seamlessly with WebSocket servers (like Flask-SocketIO or a dedicated Go/Node service), which is a key requirement for the next two quarters.

## Consequences
### Pros
- **Zero Infrastructure Expansion:** No new services to monitor, patch, or pay for.
- **Low Latency:** Redis is significantly faster for simple queueing/streaming than disk-persisted Kafka in standard configurations.
- **Consumer Groups:** Redis Streams provides native support for consumer groups, allowing us to scale notification workers horizontally.
- **Message Persistence:** Unlike Redis Pub/Sub, Streams are persistent on disk (via AOF/RDB), satisfying at-least-once requirements.

### Cons
- **Memory Constraints:** Redis is primarily RAM-based. We must implement a "trimming" strategy (MAXLEN) to prevent the stream from consuming all available memory. Long-term storage of notification history must be offloaded to PostgreSQL.
- **Manual Retry Logic:** Unlike some enterprise message brokers, we will need to implement our own visibility timeout and dead-letter queue (DLQ) logic using the `XPENDING` and `XCLAIM` commands.
- **Durability Trade-off:** Redis durability depends on AOF settings. In a catastrophic "power-off" failure, there is a slightly higher risk of data loss compared to Kafka's multi-node disk replication. We will mitigate this via the Postgres Outbox pattern for billing-critical events.

## Alternatives Considered
### Apache Kafka
- **Why Rejected:** Kafka is the industry standard for high-throughput streaming, but its operational complexity is a "force multiplier" in the wrong direction for a 6-person team. The setup, maintenance, and lack of team experience would exceed the 2-week timeline and increase the risk of misconfiguration-led outages. The cost of a managed service is also outside our current budget.
- **When to Reconsider:** If we reach a scale of >50,000 req/s or require complex stream processing (KSQL/Kafka Streams), we should evaluate a migration. Since we are using an abstraction (worker nodes), the migration path from Redis Streams to Kafka is well-understood.
