# ADR-001 — Use Redis Streams for Notification Subsystem

- **Status**: Proposed
- **Date**: 2026-05-17
- **Deciders**: Engineering Team (3 Senior, 3 Mid-level)
- **Context tags**: notifications, messaging, scalability, redis

## Context

Our current synchronous notification system is causing 8-second latency spikes, silent failures, and cascading failures due to connection pool exhaustion. We need to decouple notifications from the HTTP request cycle to support retries, delivery guarantees, and a 10x traffic growth target (up to 5,000 peak req/s).

Constraints:
- 6-person team with no dedicated infrastructure engineer.
- No existing Kafka experience.
- Must deliver value within 2 weeks.
- Modest budget; existing Redis instance is already used for sessions and rate limiting.
- Requirement for at-least-once delivery for billing events ("trial expired", "payment failed").

## Decision

We will use **Redis Streams** for the notification message bus and asynchronous processing.

> We will implement Redis Streams using Consumer Groups to handle notification delivery, leveraging our existing Redis infrastructure and team expertise.

## Rationale

Redis Streams is the optimal choice given our operational constraints and scaling targets:

1. **Operational Simplicity**: We already run Redis in production. Adding Streams introduces zero new infrastructure components. Kafka would require Zookeeper/KRaft management or a high-cost managed service (Confluent), which the team is not equipped to maintain.
2. **Time-to-Value**: The 2-week constraint makes Kafka's learning curve and configuration overhead a project risk. Redis Streams uses a simple API that the team can integrate quickly.
3. **Performance**: Redis easily handles 5,000 req/s with sub-millisecond latency. At our current 500 req/s and projected 10x growth, Redis throughput far exceeds our needs.
4. **Delivery Guarantees**: Redis Streams supports Consumer Groups with `XACK` and `XCLAIM` semantics, ensuring at-least-once delivery. For billing-critical exactly-once semantics, we will implement application-level idempotency using our existing PostgreSQL primary (storing a `notification_id` or `event_id` in a `processed_events` table).
5. **WebSocket Readiness**: Redis is natively suited for the real-time WebSocket push requirements planned for Q3/Q4, allowing us to use the same infrastructure for both task processing and real-time updates.

## Alternatives Considered

- **Apache Kafka**: Rejected. While Kafka offers superior long-term message retention and a richer ecosystem for stream processing, the operational burden (cluster management, partition tuning, rebalancing) is too high for a 6-person team without a DevOps lead. The cost of a managed Kafka provider at our scale exceeds our "modest" budget constraint.
- **PostgreSQL (as a queue)**: Rejected. While it would provide the strongest ACID guarantees for exactly-once billing events, the 500-5,000 req/s throughput requirements and the need for low-latency WebSocket pushes make a dedicated memory-resident stream a better architectural fit.

## Consequences

- **Positive**: 
    - Zero new infrastructure overhead.
    - Low latency processing for all notification types.
    - Simple path to implementing retries and Dead Letter Queues (DLQ) by moving failed messages to a secondary stream.
- **Negative**:
    - Memory Constraints: Since Redis is in-memory, we must implement strict message retention policies (e.g., `XTRIM` with `MAXLEN`) to prevent OOM errors.
    - Data Persistence: Unlike Kafka, which is disk-first, Redis persistence (AOF/RDB) must be carefully tuned to ensure data isn't lost during a crash, though this is acceptable for notifications which can be regenerated from DB state if catastrophic failure occurs.
- **Follow-ups**:
    - Implement a `NotificationWorker` pattern in the Flask monolith using `redis-py`.
    - Configure Redis AOF (Append Only File) with `fsync everysec` to balance persistence and performance.
    - Create a schema for the `processed_events` table in PostgreSQL to handle idempotency for billing notifications.

## Backlinks

- [System Context: Notifier Subsystem Decision](system_context.md)
