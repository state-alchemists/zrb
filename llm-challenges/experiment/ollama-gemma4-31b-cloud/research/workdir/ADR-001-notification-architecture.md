# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context
The current notification system is synchronous and embedded within the HTTP request cycle, leading to request timeouts (spikes up to 8s), silent failures of emails/webhooks, and cascading failures due to connection pool exhaustion. There are currently no delivery guarantees for billing-critical notifications.

The system must evolve to:
- Decouple notifications from the request cycle.
- Support retries with exponential backoff.
- Guarantee at-least-once delivery (and exactly-once where feasible) for billing events.
- Support future WebSocket push notifications.
- Scale to 10x current traffic (~5,000 req/s peak).

**Constraints:**
- Small team (6 engineers), no dedicated DevOps/Infra engineer.
- No existing Kafka expertise.
- Existing Redis deployment in production.
- Tight timeline: < 2 weeks for initial value.
- Modest budget; no expensive managed Kafka services.

## Decision
We will use **Redis Streams** for the notification subsystem.

### Justification
Given the team's composition and current infrastructure, Redis Streams provide the optimal balance between technical requirements and operational feasibility.

1. **Operational Simplicity**: We already operate Redis. Adding Streams requires no new infrastructure components, whereas Kafka would introduce a heavy dependency (ZooKeeper/KRaft, JVM tuning, complex partitioning) that the team is not equipped to manage without a dedicated infra engineer.
2. **Throughput and Latency**: At a peak of 500 req/s (and 5,000 req/s at 10x growth), Redis Streams easily handles the load. Kafka is designed for millions of events per second, which is overkill for this scale.
3. **Consumer Groups**: Redis Streams supports Consumer Groups (XGROUP), providing the same basic scaling and load-balancing capabilities as Kafka, allowing us to scale the number of notification workers independently.
4. **Delivery Guarantees**: By utilizing the Pending Entries List (PEL) and explicit acknowledgments (`XACK`), we can ensure at-least-once delivery. For "exactly-once" billing notifications, we will implement idempotency keys at the application level (database-backed), which is a requirement regardless of the broker chosen.
5. **Time to Value**: Leveraging an existing Redis instance allows for a migration that can be completed within the 2-week window, as it requires only library updates and logic changes rather than cluster deployment and stabilization.

## Consequences

### Pros
- **Near-zero operational overhead**: No new servers or complex clustering to manage.
- **Low Latency**: In-memory processing ensures minimal overhead for the producer.
- **Unified Stack**: Keeps the infrastructure lean, reducing the "cognitive load" for the 6-person team.
- **Fast Implementation**: Rapid transition from synchronous to asynchronous processing.

### Cons
- **Memory Limitations**: Unlike Kafka's disk-based persistence, Redis stores the stream in memory (though it can persist to disk via RDB/AOF). We must implement a strict capping policy (`XADD ... MAXLEN ~`) to prevent memory exhaustion.
- **Less Robust Ecosystem**: Kafka has a richer ecosystem for complex stream processing (Kafka Connect, KSQL), though the current requirements do not necessitate these.
- **Persistence Risk**: While AOF provides durability, it is generally less robust for massive historical data retention than Kafka's segmented logs.

## Alternatives Considered

### Apache Kafka
**Rejected.**
While Kafka provides superior durability, massive scalability, and stronger "exactly-once" semantics via its transactional API, the operational cost is too high for this team.
- **Complexity**: Managing a Kafka cluster (even a small one) requires significant expertise in JVM tuning and partition management.
- **Resource Heavy**: Kafka's footprint is significantly larger than Redis.
- **Learning Curve**: With zero Kafka experience on a 6-person team, the "2-week setup" constraint would be impossible to meet.
- **Cost**: Managed options (Confluent) exceed the current budget, and self-hosting increases the risk of instability.
