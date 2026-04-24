# ADR 001: Notification Subsystem Architecture

## Status
Proposed

## Context
The current notification system is implemented synchronously within the Flask monolith's request cycle. This has led to request timeouts (up to 8s), silent failures during provider outages, and cascading failures due to connection pool exhaustion. 

We need a decoupled, asynchronous system that supports:
- Retries with exponential backoff.
- At-least-once delivery for general events and exactly-once semantics for billing-critical notifications.
- Future support for WebSocket push notifications.
- Scalability to handle 10x current peak traffic (~5,000 req/s).

Constraints include a small team (6 engineers) with no dedicated DevOps/Infra resource, no existing Kafka expertise, and a tight 2-week implementation window. Redis is already present in the production stack.

## Decision
We will use **Redis Streams** as the backbone for the notification subsystem.

### Justification
1. **Operational Simplicity**: The team already manages Redis for session and rate limiting. Adding Streams requires no new infrastructure, avoiding the significant "Day 2" operational burden (Zookeeper/KRaft, JVM tuning, partition management) associated with self-hosting Kafka.
2. **Resource Efficiency**: At 500-5,000 req/s, Redis Streams easily handles the throughput without the overhead of a heavyweight distributed log.
3. **Consumer Groups**: Redis Streams provides consumer groups, enabling the horizontal scaling of notification workers and ensuring messages are distributed across the 4 (or more) web servers.
4. **Delivery Guarantees**: By leveraging `XACK` (acknowledgments) and `XPENDING`, we can implement the required at-least-once delivery and retry logic. Exactly-once semantics for billing will be achieved through **idempotency keys** at the application level (checking a `processed_notification_id` in PostgreSQL), as neither Redis nor Kafka provides true end-to-end exactly-once delivery without significant complexity.
5. **Time-to-Value**: Given the existing Redis deployment, the "setup" time is near zero, allowing the team to meet the 2-week migration deadline.

## Consequences
### Pros
- **Zero Infrastructure Overhead**: No new binaries to install or clusters to manage.
- **Low Latency**: Extremely fast append and read operations.
- **Rapid Implementation**: The team can leverage existing Redis client libraries in Python.
- **Future-Proof**: Well-positioned for WebSocket integration, as Redis is already a common choice for pub/sub and state tracking for sockets.

### Cons
- **Memory Constraints**: Unlike Kafka, which persists to disk efficiently, Redis is primarily in-memory. We will need to strictly manage stream length using `MAXLEN` to prevent OOM crashes.
- **Persistence Risk**: While Redis offers AOF/RDB, it is generally less durable than Kafka's distributed commit log. We will mitigate this by ensuring critical billing events are persisted to PostgreSQL before being queued in the stream (the Transactional Outbox pattern).

## Alternatives Considered
### Apache Kafka
Kafka was rejected for the following reasons:
- **Operational Complexity**: Managing a Kafka cluster without a dedicated infrastructure engineer is a high-risk move for a 6-person team. 
- **Onboarding Cost**: No one on the team has Kafka experience; the learning curve for partitioning, offsets, and consumer group rebalancing would exceed the 2-week window.
- **Overkill**: While Kafka scales better than Redis, it is designed for millions of events per second. Our 10x target (5k req/s) is well within Redis's capabilities.
- **Cost**: Managed solutions (Confluent) exceed the current budget.
