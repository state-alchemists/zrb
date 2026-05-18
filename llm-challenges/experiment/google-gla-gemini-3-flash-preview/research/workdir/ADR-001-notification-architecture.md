# ADR-001: Notification Subsystem Architecture

**Status**: Proposed

## Context
Our SaaS project management platform currently handles notifications (emails/webhooks) synchronously, causing 8s response spikes and cascading failures. We need to decouple this process and scale from 500 req/s to 5,000 req/s while ensuring at-least-once delivery for all events and exactly-once semantics for billing-critical notifications. 

The engineering team consists of 6 people with no dedicated infrastructure engineer. We currently run Redis for caching but have zero internal experience with Apache Kafka. Our budget is modest, and we require a production-ready solution within two weeks.

## Decision
We will use **Redis Streams** for the notification subsystem.

**Justification:**
- **Operational Complexity**: Redis is already in our stack. Deploying and managing Kafka (or its Zookeeper/KRaft dependencies) would require significant training and overhead that our 6-person team cannot afford.
- **Throughput**: Redis Streams comfortably handles our 500 req/s peak and is more than capable of reaching our 5,000 req/s target on a single instance, whereas Kafka's horizontal scaling is unnecessary for this load.
- **Consumer Groups**: Redis Streams provides `XGROUP` and `XREADGROUP` commands, offering native consumer group support equivalent to Kafka for load balancing notification workers.
- **Exactly-Once Semantics**: While Kafka supports transactional producers, we will achieve exactly-once for billing by using Redis Streams' message IDs combined with idempotency keys in our PostgreSQL database (where the billing records reside).
- **Setup Time**: We can implement a Redis Streams-based worker pool within the 2-week constraint; a Kafka migration would likely take months to reach the same level of production stability.

## Consequences
- **Pros**:
    - Low latency (sub-millisecond) for message ingestion.
    - Zero additional infrastructure costs or new service dependencies.
    - Native support for message ordering and retries via Pending Entries List (PEL).
    - Simplified development using existing Python libraries (e.g., `redis-py`).
- **Cons**:
    - **Message Retention**: Unlike Kafka's disk-based storage, Redis is memory-resident. We must use `MAXLEN` to cap stream length to prevent memory exhaustion, meaning we cannot store massive history in the stream itself.
    - **Durability**: We rely on Redis AOF (Append Only File) persistence, which is slightly less resilient than Kafka's multi-node replication unless we invest in a high-availability Redis Sentinel or Cluster setup.

## Alternatives Considered
- **Apache Kafka**: Rejected due to high operational complexity, steep learning curve for the current team, and the inability to deploy a production-grade cluster within the two-week deadline. Kafka's massive scalability is currently "over-engineering" for our 5,000 req/s target.
- **Postgres-based Queue**: Rejected because high-frequency polling or `SKIP LOCKED` queries at 500+ req/s can cause significant database bloat and performance degradation on our primary application database.
