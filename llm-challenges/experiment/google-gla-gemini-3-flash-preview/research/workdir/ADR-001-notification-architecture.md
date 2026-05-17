# ADR 001: Notification Subsystem Architecture

- **Status**: Proposed
- **Date**: 2026-05-17
- **Deciders**: Engineering Team

## Context

Our current synchronous notification system (sending emails and webhooks within the HTTP request cycle) is failing. We face 8-second latency spikes at peak (500 req/s), silent message loss, and cascading failures due to connection pool exhaustion. 

We need an asynchronous solution that supports:
- **At-least-once delivery** for all notifications.
- **Exactly-once semantics** for billing-critical events.
- **Retry with exponential backoff**.
- **Scalability** to 10x current traffic (5,000 req/s).
- **Team constraints**: 6 developers, no dedicated DevOps/SRE, no prior Kafka experience.
- **Time constraint**: Value must be delivered within 2 weeks.

## Decision

We will use **Redis Streams** as the message backbone for the notification subsystem.

We will leverage the existing Redis production instance to implement a producer-consumer pattern using Consumer Groups. Each notification type (Email, Webhook, WebSocket) will have its own consumer group to ensure independent scaling and fault isolation.

## Rationale

Redis Streams is the optimal choice given our specific constraints:

1. **Operational Simplicity**: We already operate Redis for sessions and rate-limiting. Introducing Redis Streams adds zero new infrastructure overhead, whereas Kafka would require managing a JVM-based cluster and potentially Zookeeper/KRaft, for which the team has no expertise.
2. **Time-to-Value**: The 2-week deadline precludes the steep learning curve and configuration tuning required for a production-ready Kafka deployment. Redis Streams integration in Python is straightforward using `redis-py`.
3. **Throughput**: At 500 req/s (peak) and 5,000 req/s (target), Redis is more than capable. Redis typically handles >100,000 operations per second per shard, providing a massive head-room for our 10x growth target.
4. **Reliability**: Redis Streams provides at-least-once delivery guarantees through explicit acknowledgments (ACKs) and the Pending Entries List (PEL), allowing us to recover and retry failed processors.
5. **Exactly-Once Semantics**: While Kafka provides this natively, we can achieve the same for our billing events by using the unique Entry ID provided by `XADD` or a business-logic idempotency key stored in our existing PostgreSQL database during consumer processing.

## Consequences

### Positive
- **Low Latency**: Sub-millisecond message ingestion.
- **Resource Efficiency**: Low memory and CPU overhead compared to Kafka.
- **Simplified Observability**: The team can use existing Redis monitoring tools.
- **WebSocket Ready**: Redis Pub/Sub or Streams can easily back the planned real-time notification feature.

### Negative
- **Memory Bound**: Unlike Kafka’s disk-based storage, Redis is memory-resident. We must implement strict stream capping (`MAXLEN`) to prevent memory exhaustion, requiring us to move long-term archival/audit logs to PostgreSQL.
- **Persistence Trade-offs**: Redis AOF/RDB persistence is highly reliable but slightly less "durable by default" than Kafka’s distributed commit log.

## Alternatives Considered

### Apache Kafka
Kafka was rejected primarily due to **operational complexity** and **team constraints**. 
- **Learning Curve**: The team lacks Kafka experience; a 2-week implementation is unrealistic.
- **Cost**: Managed Kafka (e.g., Confluent or AWS MSK) is significantly more expensive than our current modest budget allows for at our scale.
- **Overkill**: Kafka is designed for gigabytes per second and trillions of messages. For a 5,000 req/s notification system, the infrastructure weight of Kafka outweighs its benefits. We would have chosen Kafka if we expected to reach 100x growth (50,000+ req/s) within the next 12 months or required multi-region replication.

## Backlinks
- [System Context](system_context.md)
