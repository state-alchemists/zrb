# ADR-001: Notification Subsystem Architecture

## Status
Proposed

## Context
The current notification system is synchronous, causing request timeouts (up to 8s), cascading failures via connection pool exhaustion, and a lack of delivery guarantees for billing-critical events. 

**Constraints:**
- **Team:** 6 engineers (no dedicated DevOps/Infra).
- **Existing Stack:** Python/Flask, PostgreSQL, Redis.
- **Traffic:** 500 req/s peak, target 10x growth (5,000 req/s).
- **Requirements:** Async processing, exponential backoff retries, at-least-once delivery for billing, exactly-once where feasible.
- **Operational Limit:** Maximum 2 weeks for setup/migration; limited budget (no managed Confluent).
- **Future Scope:** Real-time WebSocket push notifications.

## Decision
We will use **Redis Streams** for the notification subsystem.

**Justification:**
Given the current team size and existing infrastructure, the operational overhead of Kafka is unjustifiable. Redis is already running in production for sessions and rate-limiting, meaning the team has the baseline monitoring and deployment patterns needed. Redis Streams provides the necessary primitives—consumer groups, message persistence, and acknowledgement (ACK)—to decouple the HTTP cycle and implement retries and delivery guarantees.

At 5,000 req/s (10x growth), Redis Streams handles the load with ease on minimal hardware, whereas Kafka's JVM overhead and Zookeeper/KRaft complexity introduce a significant risk to the 2-week delivery timeline.

## Consequences

**Pros:**
- **Low Operational Friction:** Zero new infrastructure to provision or maintain; leverages existing Redis instances.
- **Rapid Delivery:** Minimal setup time; Python clients (redis-py) are mature and already compatible with the stack.
- **Performance:** Sub-millisecond latency for producers and consumers, fitting the requirement to resolve HTTP timeouts.
- **Scalability:** Consumer groups allow horizontal scaling of worker processes to handle peak bursts.
- **Feature Fit:** Supports the upcoming WebSocket push notifications natively via a pub/sub or stream-watching pattern.

**Cons:**
- **Memory Constraints:** Unlike Kafka's disk-first approach, Redis stores streams in RAM. We must implement strict `XADD` length capping (MAXLEN) to prevent OOMs.
- **Durability Trade-off:** While AOF provides durability, Kafka's commit log is inherently more robust for multi-day retention. We will mitigate this by archiving processed logs to PostgreSQL for billing audits.
- **Exactly-Once Complexity:** Redis Streams provides at-least-once delivery. To achieve "exactly-once" for billing, we must implement idempotency keys in the consumer layer (checked against PostgreSQL).

## Alternatives Considered

### Apache Kafka
**Reason for Rejection:**
- **Operational Complexity:** The team has zero Kafka experience. Deploying and managing a production-grade cluster (handling partitions, offsets, and rebalancing) would exceed the 2-week time limit and the team's capacity without a dedicated infra engineer.
- **Resource Heavy:** High memory/CPU footprint compared to Redis for the current traffic volume.
- **Cost:** Managed alternatives (Confluent) are outside the current budget.
- **Overkill:** While Kafka excels at massive throughput and long-term retention, the 10x growth target (~5k req/s) is well within the capabilities of a properly configured Redis Stream.
