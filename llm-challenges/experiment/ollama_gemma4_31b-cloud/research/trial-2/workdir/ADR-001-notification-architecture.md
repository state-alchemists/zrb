# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context
The current notification system is synchronous and embedded within the HTTP request cycle, leading to request timeouts (up to 8s spikes), silent failures, and cascading system failures due to slow external webhooks. 

We require an asynchronous messaging backbone to decouple these processes. Key requirements include:
- **Reliability**: At-least-once delivery for general notifications; exactly-once semantics for billing-critical events.
- **Resilience**: Support for retries with exponential backoff and Dead Letter Queues (DLQ).
- **Scalability**: Ability to handle 10x current peak traffic (~5,000 req/s).
- **Future Proofing**: Support for real-time WebSocket push notifications.

**Constraints:**
- **Team**: 6 engineers, no dedicated DevOps/Infra specialist.
- **Existing Stack**: Redis is already in production; no Kafka experience.
- **Timeline**: Minimal setup time (< 2 weeks).
- **Budget**: Limited; managed high-cost services (e.g., Confluent Cloud) are not currently feasible.

## Decision
We will use **Redis Streams** for the notification subsystem.

### Justification
The decision is driven by the intersection of operational simplicity and "sufficient" technical capability.

1. **Operational Surface Area**: We already operate Redis. Introducing Kafka would introduce a significant new piece of infrastructure requiring Zookeeper/KRaft management, JVM tuning, and new monitoring patterns. With no dedicated infra engineer, the risk of an improperly configured Kafka cluster causing downtime outweighs its theoretical benefits.
2. **Throughput & Latency**: Redis Streams can easily handle the target 5,000 req/s. Given our current peak is 500 req/s, Redis provides more than enough headroom for 10x growth without the overhead of Kafka's heavy disk-based persistence model.
3. **Consumer Groups**: Redis Streams provides consumer groups (`XGROUP`), allowing us to distribute notification processing across multiple workers, ensuring scalability and offset tracking.
4. **Exactly-Once Semantics**: While neither system provides "magic" exactly-once delivery across network boundaries, Redis allows us to implement exactly-once processing for billing events by using the existing Redis instance to store idempotency keys tied to the stream offset.
5. **Implementation Speed**: Since the team is already familiar with Redis, the "time to value" is measured in days rather than weeks of learning and configuration.

## Consequences

### Pros
- **Low Friction**: Rapid deployment using existing infrastructure.
- **Performance**: Extremely low latency for message ingestion and retrieval.
- **Unified Stack**: Reduces the number of distinct technologies the team must support.
- **WebSocket Ready**: Redis Pub/Sub can be easily integrated alongside Streams to support the upcoming WebSocket requirement.

### Cons
- **Retention Limits**: Unlike Kafka, which is designed for long-term log retention, Redis is primarily in-memory. We must implement aggressive capping (via `MAXLEN`) to prevent memory exhaustion.
- **Persistence Trade-off**: While AOF/RDB provide persistence, Redis does not offer the same rigorous durability guarantees as Kafka's distributed commit log. However, for a notification system, the risk of losing a few messages during a catastrophic crash is acceptable compared to the operational risk of Kafka.

## Alternatives Considered

### Apache Kafka
Kafka was rejected for the following reasons:
- **Overkill**: Our throughput requirements (5k req/s) do not justify the complexity of a distributed commit log.
- **Skill Gap**: The team has zero Kafka experience. The learning curve for producing, consuming, and managing partitions would breach the 2-week delivery constraint.
- **Operational Cost**: Managing a production-grade Kafka cluster without a dedicated infra engineer is a high-risk move. Managed options are currently budget-prohibitive.
- **Resource Intensive**: Kafka requires significantly more memory and disk I/O overhead than Redis, which would increase AWS costs.
